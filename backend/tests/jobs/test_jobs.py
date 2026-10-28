# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config


@pytest.fixture
async def jobs(tmp_path: Path):
    from koinon.jobs.repository import JobRepository
    from koinon.jobs.service import JobService

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'jobs.db'}",
                            "ddl-auto": "create",
                        }
                    }
                }
            }
        )
    )
    context.register_bean(JobRepository)
    context.register_bean(JobService)
    await context.start()
    try:
        yield context.get_bean(JobService), context.get_bean(JobRepository)
    finally:
        await context.stop()


async def test_idempotency_survives_service_recreation_and_rejects_changed_payload(jobs):
    from koinon.jobs.errors import JobConflict
    from koinon.jobs.service import JobService

    service, repository = jobs
    first = await service.submit("north", "source-1", "ingest", {"blob": "owned.txt"}, "key-1")
    reloaded = JobService(repository)
    second = await reloaded.submit("north", "source-1", "ingest", {"blob": "owned.txt"}, "key-1")
    assert second.id == first.id
    assert await repository.count() == 1
    with pytest.raises(JobConflict):
        await reloaded.submit("north", "source-1", "ingest", {"blob": "changed.txt"}, "key-1")
    other = await reloaded.submit("south", "source-1", "ingest", {"blob": "owned.txt"}, "key-1")
    assert other.id != first.id


async def test_lease_restart_retry_and_owner_guard(jobs):
    from koinon.jobs.errors import JobConflict

    service, repository = jobs
    job = await service.submit("north", "source-1", "ingest", {"blob": "owned.txt"}, "key-1")
    leased = await service.claim("worker-a", lease_seconds=30)
    assert leased.id == job.id and leased.attempts == 1 and leased.status == "running"
    assert await service.claim("worker-b") is None
    with pytest.raises(JobConflict):
        await service.complete("north", job.id, "worker-b", {"documents": 1})
    leased.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    await repository.save(leased)
    recovered = await service.claim("worker-b")
    assert recovered.id == job.id and recovered.attempts == 2
    await service.fail("north", job.id, "worker-b", "temporary provider outage", retry_delay=0)
    third = await service.claim("worker-c")
    assert third.attempts == 3
    await service.fail("north", job.id, "worker-c", "permanent provider failure", retry_delay=0)
    assert (await repository.find_by_id(job.id)).status == "failed"
    assert await service.claim("worker-d") is None


async def test_cancel_is_durable_and_cannot_be_overwritten_by_worker(jobs):
    from koinon.jobs.errors import JobConflict

    service, repository = jobs
    job = await service.submit("north", "source-1", "ingest", {}, "cancel")
    await service.claim("worker")
    await service.cancel("north", job.id)
    with pytest.raises(JobConflict):
        await service.complete("north", job.id, "worker", {"documents": 1})
    assert (await repository.find_by_id(job.id)).status == "cancelled"
    with pytest.raises(JobConflict):
        await service.cancel("south", job.id)
