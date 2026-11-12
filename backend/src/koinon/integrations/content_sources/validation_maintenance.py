# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reclaim transient preparation without resolving credentials or enabling synchronization."""

import asyncio
import logging
from datetime import timedelta
from time import monotonic

from pyfly.container import service
from pyfly.context.conditions import conditional_on_property
from pyfly.scheduling import scheduled

from koinon.integrations.content_sources.mapping_validation_repository import (
    SourceMappingValidationRepository,
)
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission

logger = logging.getLogger(__name__)


@service(name="content_sources.validation_maintenance")
@conditional_on_property("koinon.process.role", having_value="worker")
class SourceValidationMaintenance:
    def __init__(self, records: SourceMappingValidationRepository, admission: WorkAdmission):
        self.records, self.admission = records, admission
        self._busy = asyncio.Lock()

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        if self._busy.locked():
            return
        async with self._busy:
            try:
                await self.cleanup()
            except Exception as error:
                # Durable claim/position survives rollback. No tenant, owner, item, or provider is logged.
                logger.warning("source_validation_cleanup_failed", extra={"error_type": type(error).__name__})

    async def cleanup(self):
        """One bounded invocation; fixed-delay scheduling resumes remaining work after one second."""
        async with self.admission.hold("maintenance"):
            started = monotonic()
            for _ in range(10):
                if monotonic() - started >= 5:
                    return True
                async with asyncio.timeout(min(1, 5 - (monotonic() - started))):
                    async with primary_authority(read_only=False):
                        now = await self.records.database_time()
                        candidate = await self.records.cleanup_candidate(now)
                        if candidate is None:
                            return False
                        claim = await self.records.claim_cleanup(*candidate, now)
                if claim is not None:
                    remaining = 5 - (monotonic() - started)
                    if remaining <= 0:
                        return True
                    async with asyncio.timeout(min(1, remaining)):
                        async with primary_authority(read_only=False):
                            await self.records.cleanup_batch(claim, await self.records.database_time())
            return True
