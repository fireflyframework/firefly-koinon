# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from types import SimpleNamespace

import pytest

from koinon.assistants.worker import run_consumers
from koinon.operations.settings import OperationalSettings


async def test_configured_consumers_bound_inflight_runs_and_cancel_as_one_group():
    pending = list(range(5))
    claimed = []
    active = set()
    entered = asyncio.Event()
    release = asyncio.Event()

    class Queue:
        async def claim(self, worker_id):
            claimed.append(worker_id)
            return SimpleNamespace(id=pending.pop(0)) if pending else None

    class Executor:
        async def execute(self, run_id, worker_id):
            active.add(run_id)
            assert len(active) <= 2
            if len(active) == 2:
                entered.set()
            try:
                await release.wait()
            finally:
                active.remove(run_id)

    worker = asyncio.create_task(
        run_consumers(Queue(), Executor(), OperationalSettings(worker_concurrency=2))
    )
    await asyncio.wait_for(entered.wait(), 1)
    assert len(active) == 2 and len(claimed) == 2 and len(set(claimed)) == 2
    assert all(len(identity) <= 64 for identity in claimed)
    worker.cancel()
    with pytest.raises(asyncio.CancelledError):
        await worker
    assert not active and len(pending) == 3


async def test_unexpected_consumer_failure_stops_peers_instead_of_leaking_workers():
    peer = asyncio.Event()
    finished = asyncio.Event()

    class Queue:
        async def claim(self, worker_id):
            return SimpleNamespace(id=worker_id)

    class Executor:
        async def execute(self, run_id, worker_id):
            if worker_id.endswith("-0"):
                await peer.wait()
                raise RuntimeError("Unexpected adapter failure")
            peer.set()
            try:
                await asyncio.Event().wait()
            finally:
                finished.set()

    with pytest.raises(ExceptionGroup) as error:
        await run_consumers(Queue(), Executor(), OperationalSettings(worker_concurrency=2))
    assert any(isinstance(item, RuntimeError) for item in error.value.exceptions)
    assert finished.is_set()


async def test_configured_job_lease_reaches_native_repository_and_explicit_override_survives(tmp_path):
    from datetime import UTC, datetime

    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.jobs.repository import JobRepository
    from koinon.jobs.service import JobService

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "eda": {"provider": "memory"},
                    "agentic": {"enabled": True},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'leases.db'}",
                        }
                    },
                }
            }
        )
    )
    context.container.register_instance(OperationalSettings, OperationalSettings(job_lease_seconds=113))
    context.register_bean(JobRepository)
    context.register_bean(JobService)
    await context.start()
    try:
        service = context.get_bean(JobService)
        assert service.settings is context.get_bean(OperationalSettings)
        await service.submit("north", "asset1", "ingest", {}, "one")
        await service.submit("north", "asset2", "ingest", {}, "two")
        default = await service.claim("default-worker")
        assert default is not None and default.lease_until is not None
        assert 105 <= (default.lease_until - datetime.now(UTC)).total_seconds() <= 114
        explicit = await service.claim("explicit-worker", 7)
        assert explicit is not None and explicit.lease_until is not None
        assert 1 <= (explicit.lease_until - datetime.now(UTC)).total_seconds() <= 8
    finally:
        await context.stop()
