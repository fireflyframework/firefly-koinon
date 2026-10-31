# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextvars
import importlib
import importlib.util

import pytest


def admission(**values):
    assert importlib.util.find_spec("koinon.workers.admission") is not None, (
        "Managed queues need shared pre-claim admission"
    )
    module = importlib.import_module("koinon.workers.admission")
    return module, module.WorkAdmission(module.WorkAdmissionSettings(**values))


async def test_all_seven_queues_share_one_process_ceiling_and_fifo_order():
    module, gate = admission()
    entered, release = asyncio.Event(), asyncio.Event()
    order = []

    async def work(kind):
        async with gate.hold(kind):
            order.append(kind)
            if kind == "conversation":
                entered.set()
                await release.wait()
            assert gate.worker_active == 1

    first = asyncio.create_task(work("conversation"))
    await asyncio.wait_for(entered.wait(), 1)
    kinds = ["index", "attachment", "profile", "document", "structured", "callback"]
    tasks = [asyncio.create_task(work(kind)) for kind in kinds]
    await asyncio.sleep(0)
    assert order == ["conversation"] and gate.worker_waiting == 6
    release.set()
    await asyncio.gather(first, *tasks)
    assert order == ["conversation", *kinds]
    assert gate.worker_active == gate.worker_waiting == 0


async def test_cancelled_waiter_does_not_steal_a_permit_or_block_next_waiter():
    _, gate = admission()
    async with gate.hold("index"):
        cancelled = asyncio.create_task(gate.hold("callback").__aenter__(), context=contextvars.Context())
        await asyncio.sleep(0)
        cancelled.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled
        assert gate.worker_active == 1 and gate.worker_waiting == 0
    async with gate.hold("profile"):
        assert gate.worker_active == 1
    assert gate.worker_active == 0


async def test_timeout_and_bounded_wait_queue_do_not_affect_active_work():
    module, gate = admission(wait_timeout_seconds=0.025, max_waiters=1)
    async with gate.hold("document"):
        queued = asyncio.create_task(gate.hold("callback").__aenter__(), context=contextvars.Context())
        await asyncio.sleep(0)

        async def overflow():
            with pytest.raises(module.WorkAdmissionUnavailable):
                async with gate.hold("attachment"):
                    pytest.fail("Full waiting queue must not admit work")

        await asyncio.create_task(overflow(), context=contextvars.Context())
        with pytest.raises(module.WorkAdmissionUnavailable):
            await queued
        assert gate.worker_active == 1 and gate.worker_waiting == 0
    assert gate.worker_active == 0


async def test_nested_work_reuses_permit_and_late_child_cannot_escape_closed_root():
    module, gate = admission()
    start_child = asyncio.Event()

    async def child():
        await start_child.wait()
        with pytest.raises(module.WorkAdmissionUnavailable):
            async with gate.hold("structured"):
                pytest.fail("A detached child cannot borrow an expired root reservation")

    async with gate.hold("conversation"):
        async with gate.hold("document"):
            assert gate.worker_active == 1
        task = asyncio.create_task(child())
    start_child.set()
    await task
    assert gate.worker_active == 0


async def test_api_capacity_is_independent_and_active_cancellation_releases_once():
    _, gate = admission()
    entered = asyncio.Event()

    async def worker():
        async with gate.hold("index"):
            entered.set()
            await asyncio.Event().wait()

    task = asyncio.create_task(worker())
    await entered.wait()
    async with gate.hold("query", api=True):
        assert gate.worker_active == gate.api_active == 1
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert gate.worker_active == gate.api_active == 0
    async with gate.hold("callback"):
        assert gate.worker_active == 1


async def test_drain_rejects_waiting_and_new_roots_but_allows_active_nested_cleanup():
    module, gate = admission()
    async with gate.hold("index"):
        task = asyncio.create_task(gate.hold("callback").__aenter__(), context=contextvars.Context())
        await asyncio.sleep(0)
        gate.close_workers()
        with pytest.raises(module.WorkAdmissionUnavailable):
            await task
        async with gate.hold("document"):
            assert gate.worker_active == 1
    with pytest.raises(module.WorkAdmissionUnavailable):
        async with gate.hold("attachment"):
            pytest.fail("Drained worker cannot claim again")
    async with gate.hold("query", api=True):
        assert gate.api_active == 1


@pytest.mark.parametrize(
    "values",
    [
        dict(worker_capacity=True),
        dict(api_capacity=0),
        dict(max_waiters=0),
        dict(wait_timeout_seconds=float("nan")),
    ],
)
def test_admission_settings_reject_unsafe_or_ambiguous_values(values):
    assert importlib.util.find_spec("koinon.workers.admission") is not None, (
        "Managed queues need shared pre-claim admission"
    )
    module = importlib.import_module("koinon.workers.admission")
    with pytest.raises(ValueError):
        module.WorkAdmissionSettings(**values)


async def test_parent_exit_does_not_release_a_permit_still_borrowed_by_an_active_child():
    _, gate = admission()
    entered, release = asyncio.Event(), asyncio.Event()

    async def child():
        async with gate.hold("structured"):
            entered.set()
            await release.wait()

    async with gate.hold("conversation"):
        task = asyncio.create_task(child())
        await entered.wait()
    assert gate.worker_active == 1, "An active nested scope still owns the root permit"
    release.set()
    await task
    assert gate.worker_active == 0


async def test_cancellation_in_the_grant_turn_returns_the_assigned_permit():
    _, gate = admission()
    held = gate.hold("index")
    await held.__aenter__()

    async def waiting():
        async with gate.hold("callback"):
            await asyncio.Event().wait()

    waiter = asyncio.create_task(waiting(), context=contextvars.Context())
    await asyncio.sleep(0)
    assert gate.worker_waiting == 1
    await held.__aexit__(None, None, None)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    assert gate.worker_active == gate.worker_waiting == 0
    async with gate.hold("index"):
        assert gate.worker_active == 1
