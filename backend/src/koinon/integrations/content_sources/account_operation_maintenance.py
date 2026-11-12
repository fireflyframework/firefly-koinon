# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded account queue cleanup without credentials or provider activity."""

import asyncio
import logging
from datetime import timedelta

from pyfly.container import service
from pyfly.context.conditions import conditional_on_property
from pyfly.scheduling import scheduled

from koinon.integrations.content_sources.account_operation_repository import SourceAccountOperationRepository
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission

logger = logging.getLogger(__name__)


@service(name="content_sources.account_maintenance")
@conditional_on_property("koinon.process.role", having_value="worker")
class SourceAccountMaintenance:
    def __init__(self, records: SourceAccountOperationRepository, admission: WorkAdmission):
        self.records, self.admission = records, admission
        self._busy = asyncio.Lock()
        self._after: str | None = None

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self) -> None:
        try:
            await self.cleanup()
        except Exception as error:
            logger.warning("source_account_cleanup_failed", extra={"error_type": type(error).__name__})

    async def cleanup(self) -> int:
        """Visit up to ten tenants with one wrap and a five-second total deadline.

        The process-local cursor survives failed tenants, not process restarts. No account
        identity is logged, and cleanup never grants provider or publication authority.
        """
        if self._busy.locked():
            return 0
        changed, wrapped = 0, False
        visited: set[str] = set()
        async with self._busy:
            try:
                async with asyncio.timeout(5), self.admission.hold("maintenance"):
                    for _ in range(10):
                        async with asyncio.timeout(1), primary_authority(read_only=False, fresh=True):
                            tenant = await self.records.next_cleanup_tenant(self._after)
                        if tenant is None:
                            if wrapped or self._after is None:
                                break
                            self._after, wrapped = None, True
                            continue
                        if tenant in visited:
                            break
                        visited.add(tenant)
                        # Move before the prune transaction so a busy tenant cannot hold the traversal.
                        self._after = tenant
                        try:
                            async with asyncio.timeout(1), primary_authority(read_only=False, fresh=True):
                                count = await self.records.cleanup_tenant(tenant)
                            changed += count
                        except Exception as error:
                            logger.warning(
                                "source_account_tenant_cleanup_failed",
                                extra={"error_type": type(error).__name__},
                            )
            except TimeoutError:
                logger.warning("source_account_cleanup_deadline")
        return changed
