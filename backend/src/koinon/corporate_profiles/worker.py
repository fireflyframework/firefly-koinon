# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded native leases; provider work runs outside primary write transactions."""

import asyncio
from datetime import timedelta
from uuid import uuid4

from pyfly.container import service
from pyfly.scheduling import scheduled

from koinon.corporate_profiles.refresh import CorporateProfileRefresher
from koinon.corporate_profiles.settings import CorporateProfileSettings


@service(name="corporate_profiles.worker")
class CorporateProfileWorker:
    def __init__(self, refresher: CorporateProfileRefresher, settings: CorporateProfileSettings):
        self.refresher, self.settings = refresher, settings
        self.worker_id = "corporate-profile-" + uuid4().hex
        self._running = False

    @scheduled(fixed_delay=timedelta(seconds=15))
    async def tick(self):
        if not self.settings.worker_enabled or self._running:
            return
        self._running = True
        try:
            # Claim only the next two items so a waiting batch cannot exhaust leases.
            remaining = 25
            while remaining:
                leases = await self.refresher.claim(self.worker_id, limit=min(2, remaining))
                if not leases:
                    break
                await asyncio.gather(*(self.refresher.execute(lease) for lease in leases))
                remaining -= len(leases)
        finally:
            self._running = False
