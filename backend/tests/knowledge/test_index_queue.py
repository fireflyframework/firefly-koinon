# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta

import pytest
from pyfly.kernel import ConflictException
from test_index_persistence import index_rows as index_rows
from test_index_persistence import record

from koinon.jobs.repository import JobRepository
from koinon.jobs.service import JobService
from koinon.knowledge.indexes.entities import timestamp
from koinon.knowledge.indexes.queue import IndexQueue


async def prepared(rows):
    jobs = JobService(JobRepository())
    queue = IndexQueue(rows, jobs)
    job = await jobs.submit("tenant", "workspace", "knowledge.index", {"index_id": "target"}, "build")
    target = record("target", live="owned-workspace")
    target.status, target.job_id = "queued", job.id
    await rows.save(target)
    return queue, job


async def test_kind_filtered_claim_and_expired_restart_fence_previous_worker(index_rows):
    queue, job = await prepared(index_rows)
    unrelated = await queue.jobs.submit("tenant", "workspace", "assistant.run", {}, "chat")
    assert await queue.claim("first") == job.id
    current = await queue.jobs.repository.find_by_id(job.id)
    current.lease_until = timestamp() - timedelta(seconds=1)
    await queue.jobs.repository.save(current)
    assert await queue.claim("replacement") == job.id
    with pytest.raises(ConflictException):
        await queue.progress("tenant", job.id, "first", {"complete": True, "indexed": True})
    assert (await queue.jobs.repository.find_by_id(unrelated.id)).status == "queued"
    assert (await queue.jobs.repository.find_by_id(job.id)).worker_id == "replacement"


async def test_successful_batches_reset_failure_budget_and_only_qualified_ann_completes(index_rows):
    queue, job = await prepared(index_rows)
    for count in range(1, 5):
        assert await queue.claim("worker") == job.id
        row = await queue.progress(
            "tenant",
            job.id,
            "worker",
            {
                "complete": False,
                "indexed": False,
                "chunk_count": 5,
                "vector_count": count,
            },
        )
        assert row.status == "building"
        assert (await queue.jobs.repository.find_by_id(job.id)).attempts == 0
    assert await queue.claim("worker") == job.id
    ready = await queue.progress(
        "tenant",
        job.id,
        "worker",
        {
            "complete": True,
            "indexed": True,
            "chunk_count": 5,
            "vector_count": 5,
        },
    )
    assert ready.status == "ready" and ready.active_slot is None and ready.build_slot is None
    stored = await queue.jobs.repository.find_by_id(job.id)
    assert stored.status == "succeeded" and stored.progress == 100 and stored.worker_id is None


async def test_direct_job_cancellation_reconciles_index_and_releases_build_slot(index_rows):
    queue, job = await prepared(index_rows)
    await queue.jobs.cancel("tenant", job.id)
    assert await queue.claim("worker") is None
    row = await index_rows.find_by_id("target")
    assert row.status == "cancelled" and row.build_slot is None


async def test_final_expired_lease_fails_preserved_target_without_claiming_other_kinds(index_rows):
    queue, job = await prepared(index_rows)
    current = await queue.jobs.repository.find_by_id(job.id)
    current.status, current.attempts = "running", current.max_attempts
    current.worker_id, current.lease_until = "lost", timestamp() - timedelta(seconds=1)
    await queue.jobs.repository.save(current)
    assert await queue.claim("replacement") is None
    row = await index_rows.find_by_id("target")
    assert row.status == "failed" and row.error_code == "INDEX_WORKER_EXHAUSTED"
    assert row.native_id == "native" and row.build_slot is None
