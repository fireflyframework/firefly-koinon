# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from koinon.corporate_profiles.settings import CorporateProfileSettings
from koinon.corporate_profiles.worker import CorporateProfileWorker


async def test_worker_claims_only_immediate_pair_and_prevents_overlapping_scheduled_dispatch():
    entered = asyncio.Event()
    release = asyncio.Event()
    active = set()
    calls = []
    count = 0

    async def claim(worker_id, limit):
        nonlocal count
        assert not active, "No pending lease may wait behind a slow in-flight pair"
        assert limit <= 2
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

    worker = CorporateProfileWorker(SimpleNamespace(claim=claim, execute=execute), CorporateProfileSettings())
    task = asyncio.create_task(worker.tick())
    await entered.wait()
    await worker.tick()
    assert calls == [2] and count == 2
    release.set()
    await task
    assert count == 25 and calls == [2] * 12 + [1] and not worker._running


async def test_disabled_worker_does_not_execute_manual_or_signin_queued_work():
    refresher = SimpleNamespace(claim=AsyncMock(), execute=AsyncMock())
    worker = CorporateProfileWorker(refresher, CorporateProfileSettings(worker_enabled=False))
    await worker.tick()
    refresher.claim.assert_not_awaited()
