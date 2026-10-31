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
from koinon.workers.admission import WorkAdmission


@service(name="corporate_profiles.worker")
class CorporateProfileWorker:
    def __init__(
        self,
        refresher: CorporateProfileRefresher,
        settings: CorporateProfileSettings,
        admission: WorkAdmission,
    ):
        self.refresher, self.settings = refresher, settings
        self.admission = admission
        self.worker_id = "corporate-profile-" + uuid4().hex
        self._running = False

    @scheduled(fixed_delay=timedelta(seconds=15))
    async def tick(self):
        if not self.settings.worker_enabled or self._running:
            return
        self._running = True
        remaining = 25

        async def consume():
            nonlocal remaining
            while remaining:
                async with self.admission.hold("profile"):
                    if remaining == 0:
                        return
                    remaining -= 1
                    leases = await self.refresher.claim(self.worker_id, limit=1)
                    if not leases:
                        remaining = 0
                        return
                    await self.refresher.execute(leases[0])

        try:
            async with asyncio.TaskGroup() as tasks:
                for _ in range(2):
                    tasks.create_task(consume())
        finally:
            self._running = False
