# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Ownership and shutdown use controlled clients without provider calls."""

import asyncio
import threading
from types import SimpleNamespace

import pytest

from koinon_storage.cloud import CloudProfile, CloudStore


def profile():
    return CloudProfile(backend="gcs", gcs_bucket="owned-private")


@pytest.mark.parametrize("owns_client", [True, False])
async def test_close_is_idempotent_and_respects_explicit_client_ownership(owns_client):
    closed = []
    store = CloudStore(
        profile(), client=SimpleNamespace(close=lambda: closed.append("client")), owns_client=owns_client
    )
    store._credential = SimpleNamespace(close=lambda: closed.append("credential"))
    await asyncio.gather(store.close(), store.close())
    await store.close()
    assert closed == (["client", "credential"] if owns_client else ["credential"])
    with pytest.raises(RuntimeError, match="closed"):
        await store.head("tenant/file")
    with pytest.raises(RuntimeError, match="closed"):
        store.get_sync("tenant/file")


async def test_default_supplied_client_still_transfers_ownership():
    closed = []
    store = CloudStore(profile(), client=SimpleNamespace(close=lambda: closed.append("client")))
    await store.close()
    assert closed == ["client"]


async def test_close_always_releases_credentials_and_preserves_client_failure():
    failure = RuntimeError("client shutdown failed")
    closed = []

    def fail():
        closed.append("client")
        raise failure

    store = CloudStore(profile(), client=SimpleNamespace(close=fail))
    store._credential = SimpleNamespace(close=lambda: closed.append("credential"))
    with pytest.raises(RuntimeError) as caught:
        await store.close()
    assert caught.value is failure and closed == ["client", "credential"]
    await store.close()
    assert closed == ["client", "credential"]


async def test_shutdown_drains_active_sdk_work_rejects_new_calls_and_survives_cancellation():
    entered, release = threading.Event(), threading.Event()
    closed = []
    store = CloudStore(profile(), client=SimpleNamespace(close=lambda: closed.append("client")))

    def work():
        entered.set()
        assert release.wait(3)
        assert closed == []
        return "finished"

    operation = asyncio.create_task(store._run(work))
    assert await asyncio.to_thread(entered.wait, 2)
    shutdown = asyncio.create_task(store.close())
    for _ in range(100):
        if getattr(store, "_closing", False):
            break
        await asyncio.sleep(0)
    assert store._closing and closed == []
    with pytest.raises(RuntimeError, match="closed"):
        await store.head("tenant/new")
    shutdown.cancel()
    release.set()
    assert await operation == "finished"
    with pytest.raises(asyncio.CancelledError):
        await shutdown
    assert closed == ["client"]
    await store.close()


async def test_shutdown_does_not_occupy_sdk_worker_while_a_compound_operation_finishes(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=1)
    loop = asyncio.get_running_loop()
    entered, release = asyncio.Event(), asyncio.Event()
    closed = []
    store = CloudStore(profile(), client=SimpleNamespace(close=lambda: closed.append("client")))

    async def in_thread(function, *args, **kwargs):
        from functools import partial

        return await loop.run_in_executor(executor, partial(function, *args, **kwargs))

    monkeypatch.setattr(asyncio, "to_thread", in_thread)

    async def compound():
        with store._operation():
            assert await store._run(lambda: "write") == "write"
            entered.set()
            await release.wait()
            assert await store._run(lambda: "verified") == "verified"
            assert closed == []

    operation = asyncio.create_task(compound())
    await entered.wait()
    shutdown = asyncio.create_task(store.close())
    await asyncio.sleep(0)
    release.set()
    try:
        await asyncio.wait_for(asyncio.gather(operation, shutdown), timeout=3)
        assert closed == ["client"]
    finally:
        executor.shutdown(wait=False)
