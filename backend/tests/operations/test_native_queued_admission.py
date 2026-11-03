# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product reservations delegate bounded waiting and permits to native PyFly."""

import asyncio

import pytest
from pyfly.resilience import QueuedBulkhead

from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


async def test_all_product_pools_use_native_queue_and_nested_work_does_not_acquire_again(monkeypatch):
    acquired = []
    original = QueuedBulkhead.acquire

    async def observed(self):
        acquired.append((self.max_concurrent, self.max_waiters, self.wait_timeout_seconds))
        await original(self)

    monkeypatch.setattr(QueuedBulkhead, "acquire", observed)
    gate = WorkAdmission(
        WorkAdmissionSettings(
            worker_capacity=2,
            conversation_capacity=3,
            api_capacity=4,
            max_waiters=7,
            wait_timeout_seconds=8,
        )
    )
    async with gate.hold("document"), gate.hold("profile"):
        assert gate.worker_active == 1
    async with gate.hold("conversation"):
        assert gate.worker_active == 1
    async with gate.hold("query", api=True):
        assert gate.api_active == 1
    assert acquired == [(2, 7, 8), (3, 7, 8), (4, 7, 8)]
    assert gate.worker_active == gate.worker_waiting == gate.api_active == 0


def test_native_loop_ownership_failure_is_not_disguised_as_capacity_exhaustion():
    gate = WorkAdmission(WorkAdmissionSettings())

    async def work():
        async with gate.hold("document"):
            pass

    asyncio.run(work())
    with pytest.raises(RuntimeError, match="another event loop"):
        asyncio.run(work())
