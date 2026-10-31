# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from koinon.corporate_profiles.settings import CorporateProfileSettings
from koinon.corporate_profiles.worker import CorporateProfileWorker
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


async def test_worker_admits_each_immediate_lease_and_prevents_overlapping_scheduled_dispatch():
    entered = asyncio.Event()
    release = asyncio.Event()
    active = set()
    calls = []
    count = 0

    async def claim(worker_id, limit):
        nonlocal count
        assert limit == 1, "Every lease needs its own admission before claim"
        calls.append(limit)
        rows = list(range(count, count + limit))
        count += limit
        return rows

    async def execute(lease):
        active.add(lease)
        assert len(active) <= 2
        if lease < 2:
            if len(active) == 2:
                entered.set()
            await release.wait()
        active.remove(lease)

    worker = CorporateProfileWorker(
        SimpleNamespace(claim=claim, execute=execute),
        CorporateProfileSettings(),
        WorkAdmission(WorkAdmissionSettings(worker_capacity=2)),
    )
    task = asyncio.create_task(worker.tick())
    await entered.wait()
    await worker.tick()
    assert calls == [1, 1] and count == 2
    release.set()
    await task
    assert count == 25 and calls == [1] * 25 and not worker._running


async def test_disabled_worker_does_not_execute_manual_or_signin_queued_work():
    refresher = SimpleNamespace(claim=AsyncMock(), execute=AsyncMock())
    worker = CorporateProfileWorker(
        refresher, CorporateProfileSettings(worker_enabled=False), WorkAdmission(WorkAdmissionSettings())
    )
    await worker.tick()
    refresher.claim.assert_not_awaited()
