# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import uuid4

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.jobs.service import JobService
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSettingsInput
from koinon.organization_knowledge.service import OrganizationKnowledgeService
from koinon.organization_knowledge.transitions.dtos import (
    KnowledgeModeIndexRecovery,
    KnowledgeModeRecoveryPage,
    KnowledgeModeRecoveryReceipt,
    KnowledgeModeTargetPage,
    KnowledgeModeTargetView,
    transition_view,
)
from koinon.organization_knowledge.transitions.entities import KnowledgeModeTransition, now
from koinon.organization_knowledge.transitions.index_attempts import ModeIndexAttemptRepository
from koinon.organization_knowledge.transitions.index_recovery import ModeIndexRecoveryService
from koinon.organization_knowledge.transitions.repositories import (
    ModeTargetRepository,
    ModeTransitionRepository,
)
from koinon.security.authority import primary_authority


@service(name="organization_knowledge.mode_transition_service")
class KnowledgeModeTransitions:
    def __init__(
        self,
        settings: OrganizationKnowledgeService,
        records: ModeTransitionRepository,
        jobs: JobService,
        targets: ModeTargetRepository,
        indexes: KnowledgeIndexRepository,
        recovery: Provider[ModeIndexRecoveryService | None] | None = None,
        attempts: ModeIndexAttemptRepository | None = None,
    ):
        self.settings, self.records, self.jobs, self.targets = settings, records, jobs, targets
        self.indexes, self.recovery = indexes, recovery
        self.attempts = attempts

    async def authority(self, subject, tenant_id):
        await self.settings.catalog.authorize(subject, tenant_id, "settings:write")

    async def scoped(self, subject, tenant_id, identifier, *, lock=False):
        await self.authority(subject, tenant_id)
        rows = await self.records.find_all(id=identifier, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("Knowledge preparation is unavailable", code="ACCESS_DENIED")
        return await self.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE) if lock else rows[0]

    async def view(self, subject, row):
        snapshot = await self.settings.snapshot(subject, row.tenant_id)
        job = await self.jobs.repository.find_by_id(row.job_id)
        pending = (
            0
            if self.activation_worker_active(row, job)
            else await self.records.pending_recovery_count(row.tenant_id, row.id)
        )
        result = transition_view(
            row, active_mode=snapshot.documents.answer_mode, pending_index_recoveries=pending
        )
        if row.status == "cancelled" and pending:
            result = result.model_copy(
                update={
                    "error_code": "MODE_INDEX_RECOVERY_REQUIRED",
                    "error": (
                        "Mode change cancelled. Complete or restore the recorded index activations; "
                        "the active mode is unchanged."
                    ),
                }
            )
        if row.error_code == "MODE_INDEX_RECOVERY_REQUIRED" and pending == 0:
            result = result.model_copy(
                update={
                    "error_code": None,
                    "error": (
                        "The mode change remains cancelled; index reconciliation completed."
                        if row.status == "cancelled"
                        else "Index reconciliation completed. "
                        "Retry preparation to verify the current Library."
                    ),
                }
            )
        return result

    @staticmethod
    def activation_worker_active(row, job):
        return bool(
            row.status == "running"
            and job
            and job.status == "running"
            and job.lease_until
            and job.lease_until > now()
        )

    @transactional
    async def request(self, subject, tenant_id, values, idempotency_key):
        await self.authority(subject, tenant_id)
        values = OrganizationKnowledgeSettingsInput.model_validate(values)
        await self.settings.catalog.tenant_repository.find_by_id(tenant_id, lock=LockMode.PESSIMISTIC_WRITE)
        context = SecurityContextHolder.get_context()
        token = context.attributes.get("koinon_token_id") if context else None
        payload = {"subject": subject, "token_id": token, "settings": values.model_dump(mode="json")}
        previous = await self.jobs.repository.find_all(tenant_id=tenant_id, idempotency_key=idempotency_key)
        if previous:
            job = await self.jobs.submit(tenant_id, tenant_id, "knowledge.mode", payload, idempotency_key)
            rows = await self.records.find_all(tenant_id=tenant_id, job_id=job.id)
            if not rows:
                raise ConflictException(
                    "The preparation receipt is unavailable", code="KNOWLEDGE_MODE_UNAVAILABLE"
                )
            return await self.view(subject, rows[0])
        snapshot = await self.settings.snapshot(subject, tenant_id)
        if values.expected_revision != snapshot.revision:
            raise ConflictException(
                "Reload current knowledge settings", code="ORGANIZATION_KNOWLEDGE_CHANGED"
            )
        if values.documents.answer_mode == snapshot.documents.answer_mode:
            raise InvalidRequestException(
                "The requested mode is already active", code="KNOWLEDGE_MODE_UNCHANGED"
            )
        if await self.records.active(tenant_id) is not None:
            raise ConflictException("Cancel the current preparation first", code="KNOWLEDGE_MODE_IN_PROGRESS")
        if await self.records.has_pending_index_recovery(tenant_id):
            raise ConflictException(
                "Reconcile the previous mode change's pending index activation before starting another.",
                code="MODE_INDEX_RECOVERY_REQUIRED",
            )
        job = await self.jobs.submit(tenant_id, tenant_id, "knowledge.mode", payload, idempotency_key)
        row = await self.records.save(
            KnowledgeModeTransition(
                id=str(uuid4()),
                tenant_id=tenant_id,
                active_slot=tenant_id,
                job_id=job.id,
                actor=subject,
                access_token_id=token,
                base_revision=snapshot.revision,
                base_digest=snapshot.digest,
                active_mode=snapshot.documents.answer_mode,
                requested_settings=values.model_dump(mode="json"),
            )
        )
        await self.settings.catalog._audit(
            subject,
            tenant_id,
            "knowledge.mode.requested",
            row.id,
            {"job_id": job.id, "requested_mode": values.documents.answer_mode},
        )
        return await self.view(subject, row)

    async def get(self, subject, tenant_id, identifier):
        await self.settings.catalog._refresh_managed_memberships(subject)
        return await self._get(subject, tenant_id, identifier)

    @primary_authority()
    async def _get(self, subject, tenant_id, identifier):
        return await self.view(subject, await self.scoped(subject, tenant_id, identifier))

    async def current(self, subject, tenant_id):
        await self.settings.catalog._refresh_managed_memberships(subject)
        return await self._current(subject, tenant_id)

    @primary_authority()
    async def _current(self, subject, tenant_id):
        await self.authority(subject, tenant_id)
        row = await self.records.latest(tenant_id)
        return await self.view(subject, row) if row else None

    async def target_page(self, subject, tenant_id, identifier, *, after=None, limit=50):
        await self.settings.catalog._refresh_managed_memberships(subject)
        return await self._target_page(subject, tenant_id, identifier, after=after, limit=limit)

    @primary_authority()
    async def _target_page(self, subject, tenant_id, identifier, *, after=None, limit=50):
        parent = await self.scoped(subject, tenant_id, identifier)
        parent_job = await self.jobs.repository.find_by_id(parent.job_id)
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or (after is not None and (not isinstance(after, str) or not 1 <= len(after) <= 64))
        ):
            raise InvalidRequestException(
                "Select a bounded target page and valid cursor", code="INVALID_MODE_PAGE"
            )
        rows = await self.targets.page(tenant_id, identifier, after=after, limit=limit + 1)
        states = await self.targets.mode_index_states(
            tenant_id,
            identifier,
            [row.result["index_id"] for row in rows[:limit] if row.result.get("index_id")],
        )
        items = []
        for row in rows[:limit]:
            await self.settings.catalog.get(subject, tenant_id, row.catalog_id)
            fields = {
                key: row.result[key]
                for key in KnowledgeModeTargetView.model_fields
                if key in row.result
                and key not in {"id", "kind", "catalog_id", "workspace_id", "status", "error_code"}
            }
            index = states.get(fields.get("index_id"))
            if index is not None and (
                index.status == "activating" or fields.get("action") == "reconcile_index"
            ):
                descriptor = await self.recovery_receipt(subject, tenant_id, parent, parent_job, index)
                fields["index_recovery"] = descriptor
                state, message = descriptor.state, descriptor.message
                fields["action"] = "reconcile_index" if state == "required" else None
                fields["message"] = message
            job_id = fields.get("job_id")
            if job_id:
                jobs = await self.jobs.repository.find_all(tenant_id=tenant_id, id=job_id)
                job = jobs[0] if jobs else None
                fields["job_status"] = job.status if job else "unavailable"
                fields["lease_until"] = job.lease_until.isoformat() if job and job.lease_until else None
            items.append(
                KnowledgeModeTargetView(
                    id=row.id,
                    kind=row.kind,
                    catalog_id=row.catalog_id,
                    workspace_id=row.workspace_id,
                    status=row.status,
                    error_code=row.error_code,
                    **fields,
                )
            )
        return KnowledgeModeTargetPage(
            items=items,
            next_cursor=rows[limit - 1].id if len(rows) > limit else None,
        )

    async def recovery_receipt(self, subject, tenant_id, parent, parent_job, index):
        workspace = await self.settings.catalog.get(subject, tenant_id, index.workspace_id)
        active_worker = self.activation_worker_active(parent, parent_job)
        pending = index.status == "activating"
        state = "in_progress" if pending and active_worker else "required" if pending else "resolved"
        message = (
            (
                "The preparation worker is finishing this index activation. Wait for its "
                "current lease to complete."
            )
            if state == "in_progress"
            else (
                "This admitted index activation requires explicit completion or "
                "restoration. The cancelled mode change will not resume."
            )
            if state == "required" and parent.status == "cancelled"
            else (
                "This admitted index activation requires explicit completion or restoration "
                "before preparation can continue."
            )
            if state == "required"
            else "Index reconciliation completed; the mode transition state is unchanged."
        )
        observation = {"native_pointer_state": "unavailable", "actions": []}
        inspector = self.recovery.get() if self.recovery is not None else None
        blocked = workspace.status == "archived"
        if inspector is not None and workspace.status != "archived":
            try:
                observation = await inspector.inspect(subject, tenant_id, index.id)
            except ConflictException as error:
                if error.code != "INDEX_WORKSPACE_CHANGED":
                    raise
                blocked = True
                message = (
                    "This receipt belongs to a previous workspace binding. "
                    "Restore that binding before reconciling this index."
                )
        if workspace.status == "archived":
            message = (
                "This workspace is archived. Restore its authorized Library workspace "
                "before reconciling this index."
            )

        if state == "required" and not blocked:
            pointer = observation["native_pointer_state"]
            message = {
                "target": (
                    "The native index switch committed. Finish its recorded activation or "
                    "restore the previous index; neither action repeats embedding work."
                ),
                "previous": (
                    "The native pointer is still on the previous index. Restore the recorded "
                    "state without starting a new switch."
                ),
                "other": (
                    "Another native index is active. Reload and reconcile the index conflict "
                    "before continuing; no recovery action is safe from this receipt."
                ),
                "unavailable": (
                    "The native index could not be inspected. Restore its connection and reload "
                    "this receipt before choosing a recovery action."
                ),
            }[pointer] + " The mode transition is unchanged."
        if state != "required":
            observation["actions"] = []
        return KnowledgeModeIndexRecovery(
            index_id=index.id,
            job_id=index.job_id,
            state=state,
            index_status=index.status,
            **observation,
            message=message,
            activation_job_id=parent.job_id,
            activation_lease_until=parent_job.lease_until.isoformat() if active_worker else None,
        )

    async def recovery_page(self, subject, tenant_id, identifier, *, after=None, limit=50):
        await self.settings.catalog._refresh_managed_memberships(subject)
        return await self._recovery_page(subject, tenant_id, identifier, after=after, limit=limit)

    @primary_authority()
    async def _recovery_page(self, subject, tenant_id, identifier, *, after=None, limit=50):
        parent = await self.scoped(subject, tenant_id, identifier)
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or (after is not None and (not isinstance(after, str) or not 1 <= len(after) <= 64))
        ):
            raise InvalidRequestException(
                "Select a recovery page of 1 to 100 records and a valid cursor", code="INVALID_MODE_PAGE"
            )
        job = await self.jobs.repository.find_by_id(parent.job_id)
        if self.attempts is None:
            raise ConflictException("Activation receipts are unavailable", code="MODE_RECEIPTS_UNAVAILABLE")
        rows = await self.attempts.page(tenant_id, identifier, after=after, limit=limit + 1)
        resolutions = await self.attempts.resolutions(tenant_id, [row.id for row in rows[:limit]])
        indexes = await self.targets.mode_index_states(
            tenant_id, identifier, [row.index_id for row in rows[:limit]]
        )
        items = []
        for attempt in rows[:limit]:
            await self.settings.catalog.get(subject, tenant_id, attempt.workspace_id)
            resolution = resolutions.get(attempt.id)
            if resolution is None:
                raise ConflictException(
                    "The activation resolution is unavailable", code="MODE_RECEIPTS_UNAVAILABLE"
                )
            index = indexes.get(attempt.index_id)
            if (
                resolution.status == "pending"
                and index is not None
                and index.transition.get("mode_activation_attempt_id") == attempt.id
            ):
                receipt = await self.recovery_receipt(subject, tenant_id, parent, job, index)
            else:
                pending = resolution.status == "pending"
                receipt = KnowledgeModeIndexRecovery(
                    index_id=attempt.index_id,
                    job_id=attempt.job_id,
                    state="required" if pending else "resolved",
                    activation_job_id=parent.job_id,
                    activation_lease_until=None,
                    index_status="unavailable" if pending else resolution.status,
                    actions=[],
                    message=(
                        "The captured index activation no longer matches its live record. "
                        "An operator must reconcile this exact receipt; "
                        "no action is safe from the current binding."
                    )
                    if pending
                    else (
                        "This recorded activation is resolved. Later index reuse does not change its receipt."
                    ),
                )
            items.append(
                KnowledgeModeRecoveryReceipt(
                    **receipt.model_dump(),
                    receipt_id=attempt.id,
                    attempt_revision=attempt.attempt_revision,
                    resolution_revision=resolution.revision,
                    resolution=resolution.status,
                    workspace_id=attempt.workspace_id,
                    native_workspace_id=attempt.native_workspace_id,
                    native_index_id=attempt.native_id,
                    provider_id=attempt.provider_id,
                    model_id=attempt.model_id,
                )
            )
        return KnowledgeModeRecoveryPage(
            items=items, next_cursor=rows[limit - 1].id if len(rows) > limit else None
        )

    async def cancel(self, subject, tenant_id, identifier, *, expected_revision):
        await self._cancel(subject, tenant_id, identifier, expected_revision=expected_revision)
        return await self.get(subject, tenant_id, identifier)

    @transactional
    async def _cancel(self, subject, tenant_id, identifier, *, expected_revision):
        await self.settings.catalog._lock_tenant(tenant_id)
        row = await self.scoped(subject, tenant_id, identifier, lock=True)
        if type(expected_revision) is not int or expected_revision != row.revision:
            raise ConflictException("Reload preparation progress", code="KNOWLEDGE_MODE_CHANGED")
        if row.status not in {"queued", "running", "failed"}:
            raise ConflictException("Preparation is already finished", code="KNOWLEDGE_MODE_TERMINAL")
        job = await self.jobs._locked(tenant_id, row.job_id)
        await self._cancel_record(subject, row, job)

    @transactional
    async def synchronize_cancelled(self, tenant_id, identifier):
        await self.settings.catalog._lock_tenant(tenant_id)
        row = await self.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != tenant_id or row.status not in {"queued", "running", "failed"}:
            return
        job = await self.jobs._locked(tenant_id, row.job_id)
        if job.kind == "knowledge.mode" and job.status == "cancelled":
            await self._cancel_record("system:mode-worker", row, job)

    @transactional
    async def settle_cancelled_children(self, tenant_id, identifier):
        await self.settings.catalog._lock_tenant(tenant_id)
        row = await self.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != tenant_id or row.status != "cancelled":
            return
        count = await self.jobs.repository.cancel_mode_children(tenant_id, identifier)
        if count:
            row.counters = {
                **row.counters,
                "cancelled_index_jobs": row.counters.get("cancelled_index_jobs", 0) + count,
            }
            row.revision += 1
            row.updated_at = now()
            await self.records.save(row)

    async def _cancel_record(self, subject, row, job):
        tenant_id = row.tenant_id
        job.status, job.lease_until, job.worker_id = "cancelled", None, None
        row.error_code, row.error = None, None
        await self.jobs.repository.save(job)
        row.status, row.active_slot, row.updated_at = "cancelled", None, now()
        row.revision += 1
        await self.records.save(row)
        await self.settings.catalog._audit(subject, tenant_id, "knowledge.mode.cancelled", row.id)

    @transactional
    async def retry(self, subject, tenant_id, identifier, *, expected_revision):
        await self.settings.catalog._lock_tenant(tenant_id)
        row = await self.scoped(subject, tenant_id, identifier, lock=True)
        if type(expected_revision) is not int or expected_revision != row.revision:
            raise ConflictException("Reload preparation progress", code="KNOWLEDGE_MODE_CHANGED")
        if row.status != "failed" or row.active_slot != tenant_id:
            raise ConflictException("Retry a failed preparation", code="KNOWLEDGE_MODE_TERMINAL")
        snapshot = await self.settings.snapshot(subject, tenant_id)
        if (snapshot.revision, snapshot.digest) != (row.base_revision, row.base_digest):
            raise ConflictException(
                "Start preparation for the current settings", code="KNOWLEDGE_MODE_SUPERSEDED"
            )
        context = SecurityContextHolder.get_context()
        row.actor = subject
        row.access_token_id = context.attributes.get("koinon_token_id") if context else None
        job = await self.jobs._locked(tenant_id, row.job_id)
        job.status, job.attempts, job.available_at = "queued", 0, now()
        job.worker_id, job.lease_until, job.error = None, None, None
        row.status, row.error, row.error_code = "queued", None, None
        row.stage, row.cursor = "discovery", {"reconcile_targets": True}
        row.counters = {**row.counters, "retry_requests": row.counters.get("retry_requests", 0) + 1}
        row.revision += 1
        row.updated_at = now()
        await self.jobs.repository.save(job)
        await self.records.save(row)
        await self.settings.catalog._audit(subject, tenant_id, "knowledge.mode.retried", row.id)
        return await self.view(subject, row)
