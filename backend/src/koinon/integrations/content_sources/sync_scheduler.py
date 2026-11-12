# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded due work dispatches through the same owner-authorized command boundary."""

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from pyfly.container import service
from pyfly.kernel import ConflictException, ForbiddenException, ServiceUnavailableException
from pyfly.scheduling import scheduled
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import exists, select

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.mapping_entities import SourceMapping
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.settings import ContentSourceSettings
from koinon.integrations.content_sources.sync_controls import ACTIVE_RUNS
from koinon.integrations.content_sources.sync_dtos import SourceControlInput
from koinon.integrations.content_sources.sync_entities import SourceSyncRun, SourceSyncState
from koinon.knowledge.bulk.authority import execution_context
from koinon.security.authority import primary_authority

logger = logging.getLogger(__name__)


def occurrence_operation(tenant, mapping, policy, occurrence):
    if occurrence.tzinfo is None:
        raise ValueError("Scheduled occurrences require a timezone")
    identity = ["koinon.source-occurrence.v1", tenant, mapping, policy, occurrence.astimezone(UTC).isoformat()]
    return str(uuid5(NAMESPACE_URL, json.dumps(identity, separators=(",", ":"))))


@service(name="content_sources.scheduler")
class SourceScheduler:
    def __init__(self, mappings: SourceMappings, settings: ContentSourceSettings):
        self.mappings, self.settings = mappings, settings
        self._busy = asyncio.Lock()

    async def due(self, *, at=None):
        now = at or datetime.now(UTC)
        async with primary_authority(fresh=True):
            active = exists().where(SourceSyncRun.mapping_id == SourceMapping.id,
                SourceSyncRun.tenant_id == SourceMapping.tenant_id, SourceSyncRun.status.in_(ACTIVE_RUNS))
            query = select(SourceMapping.tenant_id, SourceMapping.owner, SourceMapping.id,
                SourceSyncState.accepted_policy_id, SourceSyncState.revision, SourceSyncState.next_run_at).join(
                SourceSyncState, SourceSyncState.mapping_id == SourceMapping.id).where(
                SourceMapping.tenant_id == SourceSyncState.tenant_id, SourceMapping.status == "active",
                SourceSyncState.enabled.is_(True), SourceSyncState.next_run_at <= now, ~active).order_by(
                SourceSyncState.next_run_at, SourceMapping.tenant_id, SourceMapping.id).limit(self.settings.sync_scheduler_batch_size)
            return list((await self.mappings.controls._require_session().execute(query)).all())

    @scheduled(fixed_delay=timedelta(seconds=30))
    async def tick(self):
        if not self.settings.synchronization_enabled or self._busy.locked():
            return
        self.settings.synchronization_options()
        async with self._busy:
            for tenant, owner, mapping, policy, revision, occurrence in await self.due():
                command = SourceControlInput(expected_revision=revision,
                    operation_id=occurrence_operation(tenant, mapping, policy, occurrence))
                try:
                    with SecurityContextHolder.using(execution_context(owner, None)):
                        await self.mappings.execute(owner, tenant, mapping, "sync", command, _occurrence=occurrence)
                except (SourceError, ConflictException, ForbiddenException, ServiceUnavailableException) as error:
                    # Due state remains retained; another process or the next tick can retry the same occurrence.
                    logger.info("source_schedule_not_dispatched", extra={"mapping_id": mapping,
                        "reason_code": getattr(error, "code", "SOURCE_UNAVAILABLE")})
