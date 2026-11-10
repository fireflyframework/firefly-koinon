# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reuse qualified indexes and coordinate durable, explicitly replayed build work."""

from time import monotonic

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.connections.service import embedding_fingerprint
from koinon.knowledge.indexes.activation import IndexActivation
from koinon.knowledge.indexes.dtos import IndexCreateInput, IndexPlanInput
from koinon.knowledge.indexes.lifecycle import IndexLifecycleService
from koinon.organization_knowledge.transitions.authority import ModeTargetAuthority
from koinon.organization_knowledge.transitions.index_recovery import ModeIndexRecoveryService
from koinon.organization_knowledge.transitions.progress import ModeProgress
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue, original_actor
from koinon.organization_knowledge.transitions.readiness import ModeRoleReadiness
from koinon.organization_knowledge.transitions.repositories import ModeTargetRepository


@service(name="organization_knowledge.mode_index_preparation")
class ModeIndexPreparation:
    def __init__(
        self,
        queue: ModeTransitionQueue,
        targets: ModeTargetRepository,
        authority: ModeTargetAuthority,
        roles: ModeRoleReadiness,
        progress: ModeProgress,
        lifecycle: IndexLifecycleService,
        activation: IndexActivation,
        recovery: ModeIndexRecoveryService,
    ):
        self.queue, self.targets, self.authority, self.roles = queue, targets, authority, roles
        self.progress, self.lifecycle, self.activation, self.recovery = (
            progress,
            lifecycle,
            activation,
            recovery,
        )

    async def step(self, tenant_id, identifier, worker_id):
        started = monotonic()
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "prepare_indexes" or row.requested_settings["documents"]["answer_mode"] != "rag":
            raise ConflictException("Index preparation is not current", code="KNOWLEDGE_MODE_CHANGED")
        page = await self.targets.page(
            tenant_id,
            identifier,
            kind="workspace",
            after=row.cursor.get("indexes_after"),
            limit=1,
            active_only=True,
            workspace_id=row.cursor.get("preparation_workspace"),
        )
        if not page:
            await self.progress.record(
                tenant_id, identifier, worker_id, stage="prepare_indexes", next_stage="verify", milliseconds=0
            )
            return
        target = page[0]
        try:
            with original_actor(row):
                await self.authority.check(tenant_id, identifier, worker_id, target.id)
                current = await self.roles.check(
                    row.actor,
                    tenant_id,
                    target.workspace_id,
                    "rag",
                    has_documents=target.result.get("has_documents", False),
                )
                if current != target.result.get("roles") and not (
                    target.result.get("index_id")
                    and self.activation_roles_match(target.result["roles"], current)
                ):
                    raise ConflictException(
                        "Selected model connections changed", code="KNOWLEDGE_MODE_DEPENDENCY_CHANGED"
                    )
                status, result = await self.prepare(row, target, worker_id)
                await self.authority.check(tenant_id, identifier, worker_id, target.id)
        except (ConflictException, ServiceUnavailableException) as error:
            if error.code in {
                "KNOWLEDGE_MODE_LEASE_LOST",
                "JOB_LEASE_LOST",
                "KNOWLEDGE_MODE_SUPERSEDED",
                "INDEX_MODE_PREPARATION_INACTIVE",
            }:
                raise
            await self.progress.reject(
                tenant_id,
                identifier,
                worker_id,
                target_id=target.id,
                code=error.code,
                milliseconds=int(1000 * (monotonic() - started)),
            )
            return
        await self.progress.record(
            tenant_id,
            identifier,
            worker_id,
            stage="prepare_indexes",
            target_id=target.id,
            status=status,
            result=result,
            milliseconds=int(1000 * (monotonic() - started)),
            cursor={**row.cursor, "indexes_after": target.id} if status == "ready" else row.cursor,
            delay_seconds=2 if status == "waiting" else 0,
        )

    @transactional
    async def remember(self, row, target, worker_id, values):
        await self.queue.authorize(row.tenant_id, row.id, worker_id)
        current = await self.progress.target(row.tenant_id, row.id, target.id)
        current.result = {**current.result, **values}
        await self.targets.save(current)
        target.result = current.result

    @staticmethod
    def activation_roles_match(before, after):
        if set(before) != set(after):
            return False
        changed_by_activation = {
            "assignment_id",
            "assignment_revision",
            "space_id",
            "embedding_fingerprint",
            "dimensions",
            "storage_dimensions",
        }
        return all(
            (
                {key: item for key, item in value.items() if key not in changed_by_activation}
                == {key: item for key, item in after[role].items() if key not in changed_by_activation}
            )
            if role == "documents.embedding"
            else value == after[role]
            for role, value in before.items()
        )

    async def native(self, row, target, identifier):
        return await self.lifecycle.reader.adapter.get_native(
            tenant_id=row.tenant_id,
            native_workspace_id=target.native_workspace_id,
            catalog_workspace_id=target.workspace_id,
            domain="documents",
            actor=row.actor,
            identifier=identifier,
        )

    @staticmethod
    def qualified(actual):
        return bool(actual and actual["indexed"] and actual["chunk_count"] == actual["vector_count"])

    async def prepare(self, row, target, worker_id):
        if not target.result.get("has_documents"):
            return "ready", target.result
        role = target.result["roles"]["documents.embedding"]
        data = IndexPlanInput(
            workspace_id=target.workspace_id,
            domain="documents",
            provider_id=role["provider_id"],
            model_id=role["model_id"],
            expected_dimensions=role["dimensions"],
        )
        provider, state = await self.lifecycle.reader.plan_state(row.actor, row.tenant_id, data)
        identifier = target.result.get("index_id")
        if identifier:
            return await self.existing(row, target, worker_id, identifier, state)
        if state["active_index_id"]:
            actual = await self.native(row, target, state["active_index_id"])
            if (
                self.qualified(actual)
                and actual["active"]
                and actual["space_id"] == role["space_id"]
                and actual["model_id"] == role["model_id"]
                and actual["dimensions"] == role["dimensions"]
                and actual["storage_dimensions"] == role["storage_dimensions"]
                and role["embedding_fingerprint"]
                == embedding_fingerprint(
                    provider, role["model_id"], role["dimensions"], role["storage_dimensions"]
                )
            ):
                return "ready", {**target.result, "index_id": actual["id"], "reused_index": True}
        candidates = await self.lifecycle.records.mode_ready_candidates(
            row.tenant_id,
            target.workspace_id,
            target.native_workspace_id,
            provider_id=role["provider_id"],
            model_id=role["model_id"],
            after=target.result.get("candidate_after"),
        )
        if candidates:
            candidate = candidates[0]
            actual = await self.native(row, target, candidate.id)
            if (
                self.qualified(actual)
                and candidate.embedding_fingerprint
                == embedding_fingerprint(
                    provider, candidate.model_id, candidate.dimensions, candidate.storage_dimensions
                )
                and (role["dimensions"] is None or role["dimensions"] == candidate.dimensions)
            ):
                await self.remember(
                    row,
                    target,
                    worker_id,
                    {"index_id": candidate.id, "job_id": candidate.job_id, "reused_index": True},
                )
                return await self.existing(row, target, worker_id, candidate.id, state)
            return "prepared", {**target.result, "candidate_after": candidate.id}
        return await self.create(row, target, worker_id, data, state)

    async def create(self, row, target, worker_id, data, state):
        values = target.result.get("index_create") or {
            **data.model_dump(),
            "expected_active_id": state["active_index_id"],
            "expected_connection_revision": state["expected_connection_revision"],
        }
        key = "mode-index:" + row.id + ":" + target.id + ":g" + str(target.result.get("index_generation", 0))
        _, identifier = IndexLifecycleService.identity(
            row.tenant_id, IndexCreateInput.model_validate(values), key
        )
        previous = await self.lifecycle.records.find_all(tenant_id=row.tenant_id, id=identifier)
        retry = row.counters.get("retry_requests", 0)
        if not previous and target.result.get("index_create_dispatched") == retry:
            raise ConflictException(
                "Qualification has no committed target; explicit retry may repeat provider usage",
                code="INDEX_QUALIFICATION_OUTCOME_UNKNOWN",
            )
        await self.remember(
            row, target, worker_id, {"index_create": values, "index_create_dispatched": retry}
        )
        created = await self.lifecycle.create(
            row.actor, row.tenant_id, values, key, parent_mode_transition_id=row.id
        )
        return "waiting", {
            **target.result,
            "index_id": created["index"]["id"],
            "job_id": created["job_id"],
            "action": "inspect_index_job",
            "message": (
                "The preserved index job is preparing current vectors and its physical "
                "index. The active mode is unchanged."
            ),
        }

    async def existing(self, row, target, worker_id, identifier, state):
        index = await self.lifecycle.get(row.actor, row.tenant_id, identifier)
        status = index["status"]
        result = {**target.result, "index_id": identifier, "job_id": index.get("job_id")}
        if status in {"queued", "building", "awaiting_index"}:
            return "waiting", {
                **result,
                "action": "inspect_index_job",
                "message": (
                    "The existing index job is still preparing this workspace. Wait for its "
                    "receipt; no replacement build was created."
                ),
            }
        if status in {"failed", "cancelled"}:
            return await self.resume(row, target, worker_id, index, result)
        if status == "activating":
            observed = await self.recovery.inspect(row.actor, row.tenant_id, identifier)
            pointer = observed["native_pointer_state"]
            if pointer not in {"target", "previous"}:
                raise ConflictException(
                    "Inspect the pending native activation before retrying",
                    code="MODE_INDEX_RECOVERY_REQUIRED",
                )
            action = "finish" if pointer == "target" else "restore_previous"
            recovered = await self.activation.activate(
                row.actor,
                row.tenant_id,
                identifier,
                {
                    key: observed[key]
                    for key in ("expected_revision", "expected_active_id", "expected_connection_revision")
                }
                | {"recovery": action},
            )
            if recovered["status"] != "active":
                return "prepared", result
        elif status in {"ready", "retired"}:
            if not self.qualified(await self.native(row, target, identifier)):
                return await self.resume(row, target, worker_id, index, result)
            await self.activation.activate(
                row.actor,
                row.tenant_id,
                identifier,
                {
                    "expected_revision": index["revision"],
                    "expected_active_id": state["active_index_id"],
                    "expected_connection_revision": state["expected_connection_revision"],
                },
                parent_mode_transition_id=row.id,
            )
        elif status != "active":
            raise ConflictException(
                "The recorded index state is unavailable", code="KNOWLEDGE_MODE_INDEX_NOT_READY"
            )
        roles = await self.roles.check(
            row.actor, row.tenant_id, target.workspace_id, "rag", has_documents=True
        )
        before, after = target.result["roles"], roles
        if not self.activation_roles_match(before, after):
            raise ConflictException(
                "Other model assignments changed during activation", code="KNOWLEDGE_MODE_DEPENDENCY_CHANGED"
            )
        actual = await self.native(row, target, identifier)
        if (
            actual
            and actual["active"]
            and actual["space_id"] == roles["documents.embedding"]["space_id"]
            and not self.qualified(actual)
        ):
            return "prepared", {
                **result,
                "roles": roles,
                "index_id": None,
                "job_id": None,
                "index_create": None,
                "index_create_dispatched": None,
                "candidate_after": None,
                "index_generation": target.result.get("index_generation", 0) + 1,
                "message": (
                    "New content needs a qualified replacement index. "
                    "The serving index and mode remain active."
                ),
            }
        if (
            not self.qualified(actual)
            or not actual["active"]
            or actual["space_id"] != roles["documents.embedding"]["space_id"]
        ):
            raise ConflictException(
                "The selected index is not currently serving qualified content",
                code="KNOWLEDGE_MODE_INDEX_NOT_READY",
            )
        return "ready", {
            **result,
            "roles": roles,
            "action": None,
            "message": (
                "The current document index is qualified and active; the mode change is "
                "awaiting final verification."
            ),
        }

    async def resume(self, row, target, worker_id, index, result):
        retry = row.counters.get("retry_requests", 0)
        if retry <= target.result.get("index_failure_retry", retry):
            await self.remember(row, target, worker_id, {"index_failure_retry": retry})
            raise ConflictException(
                "Inspect the exact failed or stale index before explicitly retrying preparation",
                code="INDEX_PREPARATION_REVIEW_REQUIRED",
            )
        resumed = await self.lifecycle.resume(
            row.actor,
            row.tenant_id,
            index["id"],
            index["revision"],
            "mode-resume:" + row.id + ":" + str(retry) + ":" + target.id,
            parent_mode_transition_id=row.id,
        )
        return "waiting", {**result, "job_id": resumed["job_id"], "index_failure_retry": retry}
