# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextvars
from types import SimpleNamespace

import pytest

from koinon.operations.settings import OperationalSettings
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings, WorkAdmissionUnavailable
from koinon.workers.observations import WorkerBacklog


async def test_ingestion_and_two_chats_progress_independently_without_extra_ingestion_slots():
    gate = WorkAdmission(WorkAdmissionSettings(worker_capacity=1, conversation_capacity=2))
    entered = {
        key: asyncio.Event() for key in ("document", "chat-one", "chat-two", "structured", "chat-three")
    }
    finish = {key: asyncio.Event() for key in entered}

    async def work(key, kind):
        async with gate.hold(kind):
            entered[key].set()
            await finish[key].wait()

    tasks = []
    try:
        for key, kind in (
            ("document", "document"),
            ("chat-one", "conversation"),
            ("chat-two", "conversation"),
        ):
            tasks.append(asyncio.create_task(work(key, kind)))
        await asyncio.wait_for(
            asyncio.gather(*(entered[key].wait() for key in ("document", "chat-one", "chat-two"))), 1
        )
        assert gate.worker_active == 3
        tasks.extend(
            (
                asyncio.create_task(work("structured", "structured")),
                asyncio.create_task(work("chat-three", "conversation")),
            )
        )
        await asyncio.sleep(0)
        assert gate.worker_waiting == 2
        finish["chat-one"].set()
        await asyncio.wait_for(entered["chat-three"].wait(), 1)
        assert not entered["structured"].is_set()
        finish["document"].set()
        await asyncio.wait_for(entered["structured"].wait(), 1)
    finally:
        for signal in finish.values():
            signal.set()
        await asyncio.gather(*tasks)
    assert gate.worker_active == gate.worker_waiting == 0


async def test_shutdown_cancels_both_wait_queues_and_preserves_active_cleanup():
    gate = WorkAdmission(WorkAdmissionSettings(conversation_capacity=1))
    release = asyncio.Event()

    async def hold_chat():
        async with gate.hold("conversation"):
            await release.wait()

    active = asyncio.create_task(hold_chat(), context=contextvars.Context())
    await asyncio.sleep(0)
    async with gate.hold("document"):
        chat_waiter = asyncio.create_task(hold_chat(), context=contextvars.Context())
        heavy_waiter = asyncio.create_task(
            gate.hold("structured").__aenter__(), context=contextvars.Context()
        )
        await asyncio.sleep(0)
        assert gate.worker_active == gate.worker_waiting == 2
        gate.close_workers()
        for waiter in (chat_waiter, heavy_waiter):
            with pytest.raises(WorkAdmissionUnavailable):
                await waiter
        async with gate.hold("index"):
            assert gate.worker_active == 2
    release.set()
    await active
    assert gate.worker_active == gate.worker_waiting == 0
    with pytest.raises(WorkAdmissionUnavailable):
        async with gate.hold("conversation"):
            pytest.fail("A draining worker must not claim another conversation")
    async with gate.hold("query", api=True):
        assert gate.api_active == 1


async def test_observations_report_separate_conversation_budget_and_total_process_bound():
    view = await WorkerBacklog(
        SimpleNamespace(names=lambda: []),
        OperationalSettings(worker_concurrency=8),
        SimpleNamespace(contains_type=lambda kind: False),
        WorkAdmissionSettings(worker_capacity=1, conversation_capacity=2),
    ).snapshot()
    assert view.process_capacity == 3
    assert next(row.capacity for row in view.queues if row.queue == "conversation") == 2
    assert all(row.capacity == 1 for row in view.queues if row.queue != "conversation")


@pytest.mark.parametrize("value", [-1, True, 17, 1.5])
def test_conversation_capacity_is_a_bounded_integer(value):
    with pytest.raises(ValueError):
        WorkAdmissionSettings(conversation_capacity=value)
