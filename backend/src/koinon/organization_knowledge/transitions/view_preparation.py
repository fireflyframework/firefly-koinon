# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One exact recorded-view operation per durable worker lease."""

from functools import partial
from time import monotonic

from pyfly.container import service
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.organization_knowledge.transitions.authority import ModeTargetAuthority
from koinon.organization_knowledge.transitions.document_views import ModeDocumentViews
from koinon.organization_knowledge.transitions.progress import ModeProgress
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue, original_actor
from koinon.organization_knowledge.transitions.repositories import ModeTargetRepository


@service(name="organization_knowledge.mode_view_preparation")
class ModeViewPreparation:
    def __init__(
        self,
        queue: ModeTransitionQueue,
        targets: ModeTargetRepository,
        authority: ModeTargetAuthority,
        views: ModeDocumentViews,
        progress: ModeProgress,
    ):
        self.queue, self.targets, self.authority = queue, targets, authority
        self.views, self.progress = views, progress

    async def step(self, tenant_id, identifier, worker_id):
        started = monotonic()
        row = await self.queue.authorize(tenant_id, identifier, worker_id)
        if row.stage != "repair_views" or row.requested_settings["documents"]["answer_mode"] != "rlm":
            raise ConflictException("Recorded-view preparation is not current", code="KNOWLEDGE_MODE_CHANGED")
        page = await self.targets.page(
            tenant_id,
            identifier,
            kind="document",
            after=row.cursor.get("views_after"),
            limit=1,
            active_only=True,
            workspace_id=row.cursor.get("preparation_workspace"),
        )
        if not page:
            await self.progress.record(
                tenant_id,
                identifier,
                worker_id,
                stage="repair_views",
                next_stage="verify",
                milliseconds=int(1000 * (monotonic() - started)),
            )
            return
        target = page[0]

        async def authorize():
            await self.authority.check(tenant_id, identifier, worker_id, target.id)

        try:
            with original_actor(row):
                await authorize()
                result = await self.views.prepare(
                    tenant_id=tenant_id,
                    workspace_id=target.native_workspace_id,
                    source_id=target.native_id,
                    actor=row.actor,
                    authorize=authorize,
                    publication_guard=partial(
                        self.authority.publication, tenant_id, identifier, worker_id, target.id
                    ),
                )
                await authorize()
        except (ServiceUnavailableException, ConflictException) as error:
            if error.code in {"KNOWLEDGE_MODE_LEASE_LOST", "JOB_LEASE_LOST", "KNOWLEDGE_MODE_SUPERSEDED"}:
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
            stage="repair_views",
            target_id=target.id,
            status="ready",
            result=result,
            cursor={**row.cursor, "views_after": target.id},
            milliseconds=int(1000 * (monotonic() - started)),
        )
