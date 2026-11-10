# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded workspace preflight before any source or index preparation."""

from time import monotonic

from pyfly.container import service
from pyfly.kernel import ServiceUnavailableException

from koinon.organization_knowledge.transitions.authority import ModeTargetAuthority
from koinon.organization_knowledge.transitions.progress import ModeProgress
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue, original_actor
from koinon.organization_knowledge.transitions.readiness import ModeRoleReadiness
from koinon.organization_knowledge.transitions.repositories import ModeTargetRepository


@service(name="organization_knowledge.mode_preflight")
class ModePreflight:
    def __init__(
        self,
        queue: ModeTransitionQueue,
        targets: ModeTargetRepository,
        authority: ModeTargetAuthority,
        roles: ModeRoleReadiness,
        progress: ModeProgress,
    ):
        self.queue, self.targets, self.authority = queue, targets, authority
        self.roles, self.progress = roles, progress

    async def step(self, tenant_id, identifier, worker_id):
        started = monotonic()
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        mode = row.requested_settings["documents"]["answer_mode"]
        if mode == "rlm":
            curated = await self.targets.page(
                tenant_id,
                identifier,
                kind="curated",
                limit=1,
                active_only=True,
                workspace_id=row.cursor.get("preparation_workspace"),
            )
            if curated:
                await self.progress.reject(
                    tenant_id,
                    identifier,
                    worker_id,
                    target_id=curated[0].id,
                    code="KNOWLEDGE_RLM_UNQUALIFIED",
                    milliseconds=int(1000 * (monotonic() - started)),
                )
                return
        page = await self.targets.page(
            tenant_id,
            identifier,
            kind="workspace",
            after=row.cursor.get("preflight_after"),
            limit=1,
            active_only=True,
            workspace_id=row.cursor.get("preparation_workspace"),
        )
        if not page:
            await self.progress.record(
                tenant_id,
                identifier,
                worker_id,
                stage="preflight",
                next_stage="repair_views" if mode == "rlm" else "prepare_indexes",
                milliseconds=int(1000 * (monotonic() - started)),
            )
            return
        target = page[0]
        try:
            with original_actor(row):
                await self.authority.check(tenant_id, identifier, worker_id, target.id)
                documents = await self.targets.page(
                    tenant_id,
                    identifier,
                    kind="document",
                    workspace_id=target.workspace_id,
                    limit=1,
                    active_only=True,
                )
                roles = await self.roles.check(
                    row.actor, tenant_id, target.workspace_id, mode, has_documents=bool(documents)
                )
        except ServiceUnavailableException as error:
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
            stage="preflight",
            target_id=target.id,
            status="prepared",
            result={**target.result, "roles": roles, "has_documents": bool(documents)},
            cursor={**row.cursor, "preflight_after": target.id},
            milliseconds=int(1000 * (monotonic() - started)),
        )
