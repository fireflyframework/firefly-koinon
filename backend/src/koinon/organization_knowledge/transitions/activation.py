# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only current, verified preparation may publish organization settings."""

from contextlib import AsyncExitStack
from time import monotonic

from pyfly.container import service
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException

from koinon.organization_knowledge.dtos import OrganizationKnowledgeSettingsInput
from koinon.organization_knowledge.transitions.entities import now
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue, original_actor
from koinon.organization_knowledge.transitions.readiness_fence import (
    ModeReadinessFence,
    ModeReadinessSnapshot,
)
from koinon.security.authority import primary_authority


@service(name="organization_knowledge.mode_activation")
class ModeActivation:
    def __init__(self, queue: ModeTransitionQueue, fence: ModeReadinessFence):
        self.queue, self.fence = queue, fence

    async def activate(self, tenant_id, identifier, worker_id):
        if any(current_unit_of_work(name) is not None for name in ("primary", "canon", "structured")):
            raise RuntimeError("Mode activation must own its primary commit and native readiness fence")
        row = await self.queue.transitions.records.find_by_id(identifier)
        if row is None or row.tenant_id != tenant_id:
            raise ConflictException("Preparation is unavailable", code="KNOWLEDGE_MODE_LEASE_LOST")
        with original_actor(row):
            await self.queue.transitions.settings.catalog._refresh_managed_memberships(row.actor)
            async with AsyncExitStack() as held, primary_authority(read_only=False):
                return await self._activate(tenant_id, identifier, worker_id, held)

    async def _activate(self, tenant_id, identifier, worker_id, held):
        started = monotonic()
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "activate":
            raise ConflictException("Preparation is not ready to activate", code="KNOWLEDGE_MODE_CHANGED")
        with original_actor(row):
            row, job = await self.queue.fence(tenant_id, identifier, worker_id)
            expected = ModeReadinessSnapshot.decode(row.cursor.get("verified_generations"))
            checkpoint = row.cursor.get("verification", {})
            if checkpoint.get("phase") != "settle" or checkpoint.get("watermark") != expected.encode():
                raise ConflictException(
                    "Verification has not completed", code="KNOWLEDGE_MODE_VERIFICATION_REQUIRED"
                )
            await held.enter_async_context(self.fence.hold(tenant_id, expected))
            counts = {key: value for key, value in row.counters.items() if key.startswith("verified_")}
            settings = self.queue.transitions.settings
            values = OrganizationKnowledgeSettingsInput.model_validate(row.requested_settings)
            if not await settings.settings.compare_and_swap(
                tenant_id,
                values.documents.model_dump(mode="json"),
                values.structured.model_dump(mode="json"),
                row.base_revision,
                row.actor,
                now(),
            ):
                raise ConflictException(
                    "New settings superseded preparation", code="KNOWLEDGE_MODE_SUPERSEDED"
                )
            row.status, row.active_slot = "succeeded", None
            row.cursor = {key: value for key, value in row.cursor.items() if key != "progress_reason"}
            row.revision += 1
            row.updated_at = now()
            row.counters = {**row.counters, **counts}
            row.stage_milliseconds = {
                **row.stage_milliseconds,
                "activate": row.stage_milliseconds.get("activate", 0) + int(1000 * (monotonic() - started)),
            }
            job.status, job.progress = "succeeded", 100
            job.worker_id, job.lease_until = None, None
            job.result = {"transition_id": identifier, "settings_revision": row.base_revision + 1}
            await self.queue.transitions.jobs.repository.save(job)
            await self.queue.transitions.records.save(row)
            await settings.catalog._audit(
                row.actor,
                tenant_id,
                "knowledge.mode.activated",
                identifier,
                {
                    "job_id": job.id,
                    "settings_revision": row.base_revision + 1,
                    "answer_mode": values.documents.answer_mode,
                    **counts,
                },
            )
