# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextvars
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.corporate_profiles.settings import CorporateProfileSettings
from koinon.corporate_profiles.worker import CorporateProfileWorker
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings, WorkAdmissionUnavailable


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


async def test_capacity_deferral_does_not_claim_profiles_and_the_next_tick_can_run():
    gate = WorkAdmission(WorkAdmissionSettings(wait_timeout_seconds=0.01))
    refresher = SimpleNamespace(claim=AsyncMock(return_value=[]), execute=AsyncMock())
    worker = CorporateProfileWorker(refresher, CorporateProfileSettings(), gate)
    async with gate.hold("conversation"):
        await asyncio.create_task(worker.tick(), context=contextvars.Context())
    refresher.claim.assert_not_awaited()
    refresher.execute.assert_not_awaited()
    assert not worker._running and gate.worker_active == gate.worker_waiting == 0
    await worker.tick()
    refresher.claim.assert_awaited_once()


async def test_waiting_consumer_capacity_timeout_does_not_cancel_an_admitted_profile():
    gate = WorkAdmission(WorkAdmissionSettings(wait_timeout_seconds=0.01))
    started, release = asyncio.Event(), asyncio.Event()
    completed, cancelled = [], []
    claims = [[], ["retained-lease"]]

    async def claim(*args, **kwargs):
        return claims.pop()

    async def execute(lease):
        started.set()
        try:
            await release.wait()
            completed.append(lease)
        except asyncio.CancelledError:
            cancelled.append(lease)
            raise

    worker = CorporateProfileWorker(
        SimpleNamespace(claim=claim, execute=execute), CorporateProfileSettings(), gate
    )
    task = asyncio.create_task(worker.tick())
    try:
        await started.wait()
        await asyncio.sleep(0.03)
        assert cancelled == [] and not task.done()
        release.set()
        await task
        assert completed == ["retained-lease"] and not claims
        assert not worker._running and gate.worker_active == gate.worker_waiting == 0
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_capacity_failure_after_admission_is_not_hidden_as_a_deferred_tick():
    refresher = SimpleNamespace(claim=AsyncMock(side_effect=WorkAdmissionUnavailable()))
    worker = CorporateProfileWorker(
        refresher, CorporateProfileSettings(), WorkAdmission(WorkAdmissionSettings())
    )
    with pytest.raises(ExceptionGroup) as failure:
        await worker.tick()
    assert all(isinstance(error, WorkAdmissionUnavailable) for error in failure.value.exceptions)
    refresher.claim.assert_awaited()
    assert not worker._running
