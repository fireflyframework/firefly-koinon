# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded source slices retain canonical job ownership and exact publication identities."""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import service
from pyfly.context.conditions import conditional_on_property
from pyfly.scheduling import scheduled
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import exists, select

from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationBusy,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operations import SourceAccountBusy, SourceAccountOperations
from koinon.integrations.content_sources.credentials import SourceCredentialVault
from koinon.integrations.content_sources.dtos import Account, SourceScope
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
from koinon.integrations.content_sources.reader_access import _OperationToken
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_checkpoints import SourceCheckpoints
from koinon.integrations.content_sources.sync_entities import (
    SourceFolderBinding,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_files import SourceFiles
from koinon.integrations.content_sources.sync_folders import SourceFolders
from koinon.integrations.content_sources.sync_heartbeat import SourceSyncHeartbeat
from koinon.integrations.content_sources.sync_intake import retained_admission
from koinon.integrations.content_sources.sync_replacement import SourceReplacements
from koinon.integrations.content_sources.sync_runs import SourceRunLease, SourceRunRepository, lost
from koinon.integrations.content_sources.sync_walk import walk_page
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.authority import execution_context
from koinon.knowledge.bulk.ports import SourceIntakeAdmission
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission

logger = logging.getLogger(__name__)


@service(name="content_sources.worker")
@conditional_on_property("koinon.process.role", having_value="worker")
class SourceSyncWorker:
    def __init__(
        self,
        mappings: SourceMappings,
        folders: SourceFolders,
        files: SourceFiles,
        replacements: SourceReplacements,
        admission: WorkAdmission,
        settings: ContentSourceSettings,
        vault: SourceCredentialVault,
        accounts: SourceAccountOperations,
        heartbeat: SourceSyncHeartbeat,
    ):
        self.mappings, self.folders, self.files, self.replacements = mappings, folders, files, replacements
        self.admission, self.settings, self.vault = admission, settings, vault
        self.accounts, self.heartbeat = accounts, heartbeat
        self.worker_id = "source-" + uuid4().hex
        self._lease: SourceRunLease | None = None
        self._busy = asyncio.Lock()

    @asynccontextmanager
    async def _unit(self, tenant, owner, run_id):
        async with primary_authority(read_only=False, fresh=True):
            session = self.mappings.controls._require_session()
            run = await session.get(SourceSyncRun, run_id)
            if run is None or run.tenant_id != tenant:
                raise lost()
            mapping, state, policy = await self.mappings._scope(owner, tenant, run.mapping_id, write=True)
            yield session, mapping, state, policy, SourceRunRepository(session=session)

    async def admit_scan(self, execution: SourceRunLease):
        """Capture the configured limit once, before any page, without inferring legacy counts."""
        self.settings.synchronization_options()
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            session, _, state, _, records = values
            _, run, _ = await records.fenced(execution, publication=True)
            if state.scan_generation != run.scan_generation:
                raise lost()
            if state.scan_max_items is None:
                if run.page_sequence != 0 or state.scan_observed_count != 0:
                    raise lost()
                state.scan_max_items = self.settings.sync_max_scan_items
                state.revision += 1
                state.updated_at = datetime.now(UTC)
                await session.flush()
            elif state.scan_max_items != self.settings.sync_max_scan_items:
                raise lost()
            return state.scan_max_items

    async def _claim(self, tenant, owner, run_id):
        async with self._unit(tenant, owner, run_id) as values:
            _, _, _, _, records = values
            connection, mapping, run = await records.identity(tenant, owner, run_id)
            job = await records._job(run)
            now = datetime.now(UTC)
            if job.available_at > now:
                self._lease = None
                return None
            current = None
            if (
                job.worker_id == self.worker_id
                and job.status == "running"
                and job.lease_until is not None
                and job.lease_until > now
            ):
                current = SourceRunLease(
                    tenant,
                    owner,
                    mapping.id,
                    run.id,
                    job.id,
                    self.worker_id,
                    job.attempts,
                    run.mapping_revision,
                    run.connection_revision,
                    run.policy_id,
                    job.lease_until,
                    run.cancel_requested_at is not None
                    or mapping.status not in {"active", "paused"}
                    or mapping.revision != run.mapping_revision
                    or connection.status != "connected"
                    or connection.revision != run.connection_revision
                    or connection.refresh_operation is not None,
                )
                if not current.reconciliation_only:
                    current = await records.renew_owned(
                        current, lease_seconds=self.settings.sync_lease_seconds
                    )
                    if current is None:
                        raise lost()
                self._lease = current
                return current
            self._lease = None
            current = await records.claim(
                tenant, owner, run_id, self.worker_id, lease_seconds=self.settings.sync_lease_seconds
            )
            self._lease = current
            return current

    async def _page(self, execution):
        async with self._account_slice(execution) as permit, self.accounts.remote(permit):
            return await self._page_with_permit(execution, permit)

    @asynccontextmanager
    async def _account_slice(self, execution):
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            _, mapping, _, _, records = values
            _, run, _ = await records.fenced(execution, publication=True)
            request = AccountOperationRequest(
                kind="synchronization",
                operation_id=execution.run_id,
                revision=run.page_sequence,
                generation=run.scan_generation,
                connection_id=mapping.connection_id,
                connection_revision=execution.connection_revision,
                owner=execution.owner,
                process_instance_id=self.worker_id,
            )
        permit = await self.accounts.acquire(execution.tenant_id, request)
        if isinstance(permit, AccountOperationBusy):
            raise SourceAccountBusy(permit.retry_after_seconds)
        try:
            yield permit
        except BaseException:
            try:
                await self.accounts.abort(permit)
            except Exception as error:
                logger.warning("source_account_cleanup_failed", extra={"error_type": type(error).__name__})
            raise

    async def _page_with_permit(self, execution, permit):
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            session, mapping, _, policy, records = values
            _, run, _ = await records.fenced(execution, publication=True)
            if run.enumeration_complete or run.counters_json.get("error_code"):
                await self.accounts.assert_current(permit, session)
                await self.accounts.finish(permit, session)
                return
            sequence, ciphertext = run.page_sequence, run.cursor_ciphertext
            request = MappingReviewInput.model_validate(policy.policy_json["request"])
        capture = await self.mappings.remote_capture(execution.owner, execution.tenant_id, mapping, policy)
        if capture.connection_revision != execution.connection_revision:
            raise lost()
        account = Account(mapping.provider, mapping.external_subject, mapping.external_tenant)
        scope = SourceScope(account, mapping.drive_id)
        grant = await self.mappings.connections.read_grant(
            execution.owner, execution.tenant_id, mapping.connection_id, account
        )
        if grant.revision != execution.connection_revision:
            raise lost()
        state = None
        if ciphertext is not None:
            retained = self.vault.decrypt(
                execution.tenant_id, execution.owner, mapping.connection_id, "sync-checkpoint", ciphertext
            )
            if retained.get("run_id") != execution.run_id or retained.get("page_sequence") != sequence:
                raise lost()
            state = retained["walk"]
        async with self.mappings.browser._source(scope, _OperationToken(account, grant.token)) as adapter:
            chosen = await adapter.get_item(mapping.root_id)
            if chosen.kind == "file" and request.recursive:
                raise lost()
            page = await walk_page(
                adapter,
                scope,
                mapping.root_id,
                recursive=request.recursive,
                excluded=tuple(request.excluded_ids),
                state=state,
                chosen_root=chosen,
            )
        await self.mappings.connections.confirm_read_grant(
            execution.owner, execution.tenant_id, mapping.connection_id, grant
        )
        if (
            await self.mappings.remote_capture(execution.owner, execution.tenant_id, mapping, policy)
            != capture
        ):
            raise lost()
        next_cursor = (
            None
            if page.next_state is None
            else self.vault.encrypt(
                execution.tenant_id,
                execution.owner,
                mapping.connection_id,
                "sync-checkpoint",
                {"run_id": execution.run_id, "page_sequence": sequence + 1, "walk": page.next_state},
            )
        )
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            session, _, _, _, records = values
            await records.fenced(execution, publication=True)
            await self.accounts.assert_current(permit, session)
            await SourceCheckpoints(session=session).append(
                execution, sequence, page, cursor_ciphertext=next_cursor
            )
            await self.accounts.finish(permit, session)

    async def _pending(self, execution):
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            session, mapping, _, policy, records = values
            await records.fenced(execution)
            # The newest observation supplies authority for a retained work identity.
            selected = (
                select(SourceSyncObservation)
                .join(SourceSyncWork, SourceSyncWork.id == SourceSyncObservation.work_id)
                .where(
                    SourceSyncObservation.tenant_id == execution.tenant_id,
                    SourceSyncObservation.run_id == execution.run_id,
                    SourceSyncWork.status.in_(("admitted", "processing")),
                    SourceSyncObservation.remote_version.is_not(None),
                )
                .distinct(SourceSyncObservation.object_id)
                .order_by(
                    SourceSyncObservation.object_id,
                    SourceSyncObservation.page_sequence.desc(),
                    SourceSyncObservation.item_sequence.desc(),
                )
                .subquery()
            )
            from sqlalchemy.orm import aliased

            observations = aliased(SourceSyncObservation, selected)
            rows = list(
                (
                    await session.scalars(
                        select(observations)
                        .order_by(observations.page_sequence, observations.item_sequence)
                        .limit(100)
                    )
                ).all()
            )
            request = MappingReviewInput.model_validate(policy.policy_json["request"])
            parents = {
                row.event_json["ancestry"][-1]
                for row in rows
                if request.hierarchy == "preserve"
                and row.event_json.get("ancestry")
                and row.event_json["ancestry"][-1] != mapping.root_id
            }
            bindings = (
                dict(
                    (
                        await session.execute(
                            select(
                                SourceFolderBinding.remote_folder_id, SourceFolderBinding.local_folder_id
                            ).where(
                                SourceFolderBinding.tenant_id == execution.tenant_id,
                                SourceFolderBinding.mapping_id == mapping.id,
                                SourceFolderBinding.remote_folder_id.in_(parents),
                            )
                        )
                    ).all()
                )
                if parents
                else {}
            )
            result = []
            for row in rows:
                ancestry = row.event_json.get("ancestry", [])
                parent = mapping.parent_id
                if request.hierarchy == "preserve" and ancestry and ancestry[-1] != mapping.root_id:
                    parent = bindings.get(ancestry[-1])
                    if parent is None:
                        raise lost()
                result.append(
                    SourceIntakeAdmission(
                        execution.tenant_id,
                        execution.owner,
                        mapping.id,
                        execution.mapping_revision,
                        execution.connection_revision,
                        execution.run_id,
                        (mapping.workspace_id, mapping.project_id, parent),
                        (SourceCheckpoints.pin(row),),
                    )
                )
            return tuple(result)

    async def _defer(self, tenant, owner, run_id, execution, *, retry_after=None):
        """Delay one failed slice without touching another live worker or its command identity."""
        async with primary_authority(read_only=False, fresh=True):
            session = self.mappings.controls._require_session()
            run = await session.scalar(
                select(SourceSyncRun)
                .join(SourceMapping, SourceMapping.id == SourceSyncRun.mapping_id)
                .where(
                    SourceSyncRun.id == run_id,
                    SourceSyncRun.tenant_id == tenant,
                    SourceMapping.tenant_id == tenant,
                    SourceMapping.owner == owner,
                )
                .with_for_update(of=SourceSyncRun)
                .execution_options(populate_existing=True)
            )
            if run is None:
                return False
            job = await session.scalar(
                select(Job)
                .where(
                    Job.id == run.job_id,
                    Job.tenant_id == tenant,
                    Job.resource_id == run.mapping_id,
                    Job.kind == "content.source.reconcile",
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if job is None:
                return False
            now = datetime.now(UTC)
            if (
                run.cancel_requested_at is not None
                or run.status not in {"queued", "running", "reconciling"}
                or job.status not in {"queued", "running"}
                or job.worker_id not in {None, self.worker_id}
                and job.lease_until is not None
                and job.lease_until > now
                or execution is not None
                and (job.id, job.worker_id, job.attempts)
                != (execution.job_id, execution.worker_id, execution.attempt)
            ):
                return False
            delay = (
                min(300, max(1, self.settings.metadata_timeout_seconds))
                if retry_after is None
                else retry_after
            )
            job.available_at = max(job.available_at, now + timedelta(seconds=delay))
            job.updated_at = now
            return True

    async def dispatch(self, admission: SourceIntakeAdmission, execution: SourceRunLease):
        """Never turn an enqueue or native commit into a canonical acknowledgement."""
        admission = retained_admission(asdict(admission))
        if len(admission.items) != 1 or (
            admission.tenant_id,
            admission.owner,
            admission.mapping_id,
            admission.run_id,
            admission.mapping_revision,
            admission.connection_revision,
        ) != (
            execution.tenant_id,
            execution.owner,
            execution.mapping_id,
            execution.run_id,
            execution.mapping_revision,
            execution.connection_revision,
        ):
            raise lost()
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            session, _, _, _, records = values
            _, run, job = await records.fenced(execution)
            pin = admission.items[0]
            work = await session.get(SourceSyncWork, pin.work_id)
            origin = await session.get(SourceObject, pin.object_id)
            if (
                work is None
                or origin is None
                or (work.tenant_id, work.mapping_id, work.object_id, work.generation)
                != (admission.tenant_id, admission.mapping_id, pin.object_id, pin.generation)
            ):
                raise lost()
            attempt = await session.get(SourceImportAttempt, work.attempt_id) if work.attempt_id else None
            if attempt is not None and attempt.intake_item_id is not None:
                # The existing Bulk worker owns exact native inspection/ACK. Creating
                # another intake or a synthetic Bulk lease would replay its command.
                return "unresolved"
            prior = await session.scalar(
                select(SourceImportAttempt.id)
                .where(
                    SourceImportAttempt.tenant_id == execution.tenant_id,
                    SourceImportAttempt.object_id == origin.id,
                )
                .limit(1)
            )
            cancelled = execution.reconciliation_only or run.cancel_requested_at is not None
            if cancelled and attempt is None:
                return "unresolved"
            kind = origin.remote_kind
        if attempt is not None or prior is not None:
            result = await self.replacements.execute(admission, execution)
            if result.outcome != "acknowledged":
                return result.outcome
            async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
                session, _, _, _, records = values
                await records.fenced(execution)
                work = await session.get(SourceSyncWork, pin.work_id)
                header = await session.get(SourcePublicationBaseline, result.attempt_id)
                if (
                    work.attempt_id != result.attempt_id
                    or work.status != "imported"
                    or header is None
                    or not header.acknowledgement_json
                ):
                    raise lost()
            return "acknowledged"
        if kind == "folder":
            await self.folders.publish(admission, execution)
            return "acknowledged"
        await self.files.intake(admission, execution)
        return "unresolved"

    async def _finish(self, execution):
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            session, mapping, _, policy, records = values
            _, run, job = await records.fenced(execution)
            cancelled = run.cancel_requested_at is not None or execution.reconciliation_only
            complete, blocked = run.enumeration_complete, run.counters_json.get("error_code")
            processing = await session.scalar(
                select(
                    exists().where(
                        SourceSyncWork.tenant_id == execution.tenant_id,
                        SourceRunRepository._observed_work(run.id),
                        SourceSyncWork.status == "processing",
                    )
                )
            )
            if processing:
                run.status = "reconciling"
                # Fairness advances for a performed source slice, never for lease maintenance.
                job.updated_at = datetime.now(UTC)
                return run.status
        capture = None
        if complete and not cancelled and not blocked:
            async with self._account_slice(execution) as permit:
                async with self.accounts.remote(permit):
                    capture = await self.mappings.remote_capture(
                        execution.owner, execution.tenant_id, mapping, policy
                    )
                return await self._finish_captured(execution, capture, blocked, cancelled, complete, permit)
        return await self._finish_captured(execution, capture, blocked, cancelled, complete)

    async def _finish_captured(self, execution, capture, blocked, cancelled, complete, permit=None):
        async with self._unit(execution.tenant_id, execution.owner, execution.run_id) as values:
            session, _, _, _, records = values
            _, run, job = await records.fenced(execution)
            if permit is not None:
                await self.accounts.assert_current(permit, session)
            if blocked and not cancelled:
                unresolved = await session.scalar(
                    select(
                        exists().where(
                            SourceSyncWork.tenant_id == execution.tenant_id,
                            SourceRunRepository._observed_work(run.id),
                            SourceSyncWork.status.in_(("admitted", "processing")),
                        )
                    )
                )
                if not unresolved:
                    now = datetime.now(UTC)
                    run.status, run.finished_at, run.updated_at = "failed", now, now
                    job.status, job.error, job.worker_id, job.lease_until = "failed", blocked, None, None
                else:
                    run.status = "reconciling"
            elif cancelled or complete:
                await records.finish(execution, capture=capture)
            if permit is not None:
                await self.accounts.finish(permit, session)
            if run.status in {"running", "reconciling"}:
                job.updated_at = datetime.now(UTC)
            return run.status

    async def run_once(self, tenant: str, owner: str, run_id: str):
        if not self.settings.synchronization_enabled:
            return "disabled"
        self.settings.synchronization_options()
        async with self._busy, self.admission.hold("maintenance"):
            with SecurityContextHolder.using(execution_context(owner, None)):
                execution = None
                slot = self.heartbeat.reserve(tenant, owner, run_id)
                if slot is None:
                    return "unavailable"
                try:
                    execution = await self._claim(tenant, owner, run_id)
                    if execution is None:
                        return "unavailable"
                    if not execution.reconciliation_only:
                        self.heartbeat.register(slot, execution)
                        self.heartbeat.attach(execution)
                    timeout = min(
                        self.settings.transfer_timeout_seconds,
                        (execution.expires_at - datetime.now(UTC)).total_seconds() - 10,
                    )
                    if timeout <= 0:
                        raise lost()
                    async with asyncio.timeout(timeout):
                        pending = await self._pending(execution)
                        if not pending and not execution.reconciliation_only:
                            await self.admit_scan(execution)
                            await self._page(execution)
                            pending = await self._pending(execution)
                        for admission in pending:
                            await self.dispatch(admission, execution)
                        status = await self._finish(execution)
                    if status not in {"running", "reconciling"} or execution.reconciliation_only:
                        self._lease = None
                        self.heartbeat.release(execution)
                    return status
                except Exception as error:
                    self._lease = None
                    self.heartbeat.discard(slot)
                    if isinstance(error, SourceAccountBusy):
                        await self._defer(
                            tenant, owner, run_id, execution, retry_after=error.retry_after_seconds
                        )
                    else:
                        await self._defer(tenant, owner, run_id, execution)
                    if execution is not None:
                        self.heartbeat.release(execution)
                    raise
                except BaseException:
                    self._lease = None
                    self.heartbeat.discard(slot)
                    if execution is not None:
                        self.heartbeat.release(execution)
                    raise
                finally:
                    self.heartbeat.abandon(slot)
                    if execution is not None:
                        self.heartbeat.detach(execution)

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        if not self.settings.synchronization_enabled or self._busy.locked():
            return
        try:
            async with primary_authority(fresh=True):
                session = self.mappings.controls._require_session()
                now = datetime.now(UTC)
                candidate = (
                    await session.execute(
                        select(SourceSyncRun.tenant_id, SourceMapping.owner, SourceSyncRun.id)
                        .join(SourceMapping, SourceMapping.id == SourceSyncRun.mapping_id)
                        .join(Job, Job.id == SourceSyncRun.job_id)
                        .where(
                            SourceMapping.tenant_id == SourceSyncRun.tenant_id,
                            Job.tenant_id == SourceSyncRun.tenant_id,
                            Job.resource_id == SourceSyncRun.mapping_id,
                            Job.kind == "content.source.reconcile",
                            SourceSyncRun.status.in_(("queued", "running", "reconciling")),
                            Job.status.in_(("queued", "running")),
                            Job.available_at <= now,
                            (
                                (Job.worker_id == self.worker_id)
                                & (Job.status == "running")
                                & (Job.lease_until > now)
                            )
                            | (
                                (Job.attempts < Job.max_attempts)
                                & (Job.lease_until.is_(None) | (Job.lease_until <= now))
                            ),
                        )
                        .order_by(Job.updated_at, Job.available_at, SourceSyncRun.tenant_id, SourceSyncRun.id)
                        .limit(1)
                    )
                ).first()
            if candidate is not None:
                await self.run_once(*candidate)
        except Exception as error:
            logger.warning("source_worker_slice_failed", extra={"error_type": type(error).__name__})
