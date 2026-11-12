# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Lease maintenance preserves durable ownership without changing work ordering."""

import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, select
from test_sync_worker import empty_listing as empty_listing
from test_sync_worker import lifecycle as lifecycle
from test_sync_worker import review as review
from test_sync_worker import source_database as source_database
from test_sync_worker import worker as worker

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.integrations.content_sources.mapping_policies import SourcePolicies
from koinon.integrations.content_sources.sync_dtos import (
    SourceControlInput,
    SourcePolicyApplyInput,
    SourcePolicyReviewInput,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceSyncRun,
    SourceSyncState,
)
from koinon.integrations.content_sources.sync_runs import SourceRunRepository
from koinon.jobs.entities import Job
from koinon.security.authority import primary_authority

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_repeated_owned_claim_preserves_fairness_and_attempt(worker):
    lease = await worker.worker._claim("tenant", "issuer|alice", worker.run_id)
    assert lease is not None
    async with primary_authority(fresh=True):
        session = worker.mappings.controls._require_session()
        run = await session.get(SourceSyncRun, worker.run_id)
        job = await session.get(Job, run.job_id)
        before = (job.updated_at, run.updated_at, job.attempts, job.worker_id)
    retained = await worker.worker._claim("tenant", "issuer|alice", worker.run_id)
    assert retained is not None and retained.attempt == lease.attempt
    async with primary_authority(fresh=True):
        session = worker.mappings.controls._require_session()
        run = await session.get(SourceSyncRun, worker.run_id)
        job = await session.get(Job, run.job_id)
        assert (job.updated_at, run.updated_at, job.attempts, job.worker_id) == before
        assert job.lease_until >= lease.expires_at


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_heartbeat_retains_ownership_while_real_bulk_capacity_is_held(worker):
    current = await worker.worker._claim("tenant", "issuer|alice", worker.run_id)
    original_expiry = datetime.now(UTC) + timedelta(seconds=45)
    async with primary_authority(read_only=False, fresh=True):
        session = worker.mappings.controls._require_session()
        job = await session.get(Job, current.job_id)
        job.lease_until = original_expiry
        before = (job.updated_at, job.attempts, job.worker_id)
    current = replace(current, expires_at=original_expiry)
    control = worker.worker.heartbeat
    slot = control.reserve(current.tenant_id, current.owner, current.run_id)
    control.register(slot, current)
    held, release = asyncio.Event(), asyncio.Event()

    async def native_work():
        async with worker.worker.admission.hold("bulk"):
            held.set()
            await release.wait()

    native = asyncio.create_task(native_work())
    try:
        await held.wait()
        assert worker.worker.admission.worker_active == 1
        await control.renew()
        assert not native.done() and worker.worker.admission.worker_waiting == 0
        async with primary_authority(fresh=True):
            session = worker.mappings.controls._require_session()
            job = await session.get(Job, current.job_id)
            assert job.lease_until > original_expiry + timedelta(seconds=120)
            assert (job.updated_at, job.attempts, job.worker_id) == before
        async with primary_authority(read_only=False, fresh=True):
            session = worker.mappings.controls._require_session()
            challenger = await SourceRunRepository(session=session).claim(
                "tenant",
                "issuer|alice",
                worker.run_id,
                "challenger",
                at=original_expiry + timedelta(seconds=1),
                lease_seconds=360,
            )
            assert challenger is None
    finally:
        release.set()
        await native
        await control.close()


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_owner_revocation_during_page_discards_checkpoint_and_renewal(worker, monkeypatch):
    entered, proceed = asyncio.Event(), asyncio.Event()
    original = worker.mappings.browser._source
    worker.pages.append(worker.page(0, 1))

    @asynccontextmanager
    async def blocked_source(scope, tokens):
        async with original(scope, tokens) as adapter:
            children = adapter.children

            async def blocked_children(identifier, cursor=None):
                entered.set()
                await proceed.wait()
                return await children(identifier, cursor)

            adapter.children = blocked_children
            yield adapter

    monkeypatch.setattr(worker.mappings.browser, "_source", blocked_source)
    task = asyncio.create_task(worker.worker.run_once("tenant", "issuer|alice", worker.run_id))
    try:
        await entered.wait()
        async with primary_authority(read_only=False, fresh=True):
            session = worker.mappings.controls._require_session()
            run = await session.get(SourceSyncRun, worker.run_id)
            job = await session.get(Job, run.job_id)
            original_expiry = job.lease_until
            await session.execute(delete(Membership).where(Membership.subject == "issuer|alice"))
        proceed.set()
        with pytest.raises(AccessDenied):
            await task
        await worker.worker.heartbeat.renew()
        async with primary_authority(fresh=True):
            session = worker.mappings.controls._require_session()
            run = await session.get(SourceSyncRun, worker.run_id)
            job = await session.get(Job, run.job_id)
            assert run.page_sequence == 0 and not run.enumeration_complete
            assert job.lease_until == original_expiry
        with pytest.raises(AccessDenied):
            await worker.worker.run_once("tenant", "issuer|alice", worker.run_id)
    finally:
        proceed.set()
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        await worker.worker.heartbeat.close()


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("boundary", ["cancelled", "expired"])
async def test_renewal_rejects_wrong_identity_cancelled_and_expired_jobs(worker, boundary):
    current = await worker.worker._claim("tenant", "issuer|alice", worker.run_id)
    async with primary_authority(fresh=True):
        session = worker.mappings.controls._require_session()
        job = await session.get(Job, current.job_id)
        before = (job.lease_until, job.attempts, job.updated_at)
    for changed in (
        {"tenant_id": "other"},
        {"owner": "issuer|other"},
        {"mapping_id": "other"},
        {"run_id": "other"},
        {"job_id": "other"},
        {"worker_id": "other"},
        {"attempt": current.attempt + 1},
        {"mapping_revision": current.mapping_revision + 1},
        {"connection_revision": current.connection_revision + 1},
        {"policy_id": "other"},
        {"reconciliation_only": True},
    ):
        async with primary_authority(read_only=False, fresh=True):
            session = worker.mappings.controls._require_session()
            assert (
                await SourceRunRepository(session=session).renew_owned(
                    replace(current, **changed), lease_seconds=360
                )
                is None
            )
    async with primary_authority(read_only=False, fresh=True):
        session = worker.mappings.controls._require_session()
        job = await session.get(Job, current.job_id)
        assert (job.lease_until, job.attempts, job.updated_at) == before
        revision = (await session.get(SourceSyncState, worker.mapping_id)).revision
        if boundary == "expired":
            job.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    if boundary == "cancelled":
        await worker.mappings.execute(
            "issuer|alice",
            "tenant",
            worker.mapping_id,
            "cancel",
            SourceControlInput(expected_revision=revision, operation_id=str(uuid4())),
            target_run_id=worker.run_id,
        )
    async with primary_authority(read_only=False, fresh=True):
        session = worker.mappings.controls._require_session()
        assert await SourceRunRepository(session=session).renew_owned(current, lease_seconds=360) is None
        job = await session.get(Job, current.job_id)
        if boundary == "expired":
            assert job.lease_until < datetime.now(UTC)
        else:
            assert (await session.get(SourceSyncRun, worker.run_id)).cancel_requested_at is not None


@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_all_sixty_four_registrations_receive_committed_bounded_renewal(worker):
    first = await worker.worker._claim("tenant", "issuer|alice", worker.run_id)
    current = [first]
    policies = worker.review.context.get_bean(SourcePolicies)
    for index in range(1, 64):
        root_id = f"heartbeat-root-{index}"
        worker.review.state.parents[root_id] = ("root",)
        accepted = await policies.review(
            "issuer|alice",
            "tenant",
            "browser-a",
            SourcePolicyReviewInput(
                **worker.review.request.model_dump(exclude={"root_id"}),
                root_id=root_id,
                operation_id=str(uuid4()),
            ),
        )
        await policies.apply(
            "issuer|alice",
            "tenant",
            "browser-a",
            accepted.mapping_id,
            SourcePolicyApplyInput(
                operation_id=str(uuid4()),
                expected_revision=1,
                review_id=accepted.policy_id,
                review_digest=accepted.review_digest,
            ),
        )
        queued = await worker.mappings.execute(
            "issuer|alice",
            "tenant",
            accepted.mapping_id,
            "sync",
            SourceControlInput(operation_id=str(uuid4()), expected_revision=1),
        )
        lease = await worker.worker._claim("tenant", "issuer|alice", queued.run_id)
        assert lease is not None
        current.append(lease)
    original_expiry = datetime.now(UTC) + timedelta(seconds=45)
    async with primary_authority(read_only=False, fresh=True):
        session = worker.mappings.controls._require_session()
        engine = (await session.connection()).sync_connection.engine
        for lease in current:
            (await session.get(Job, lease.job_id)).lease_until = original_expiry
    current = [replace(lease, expires_at=original_expiry) for lease in current]
    control = worker.worker.heartbeat
    for item in current:
        slot = control.reserve(item.tenant_id, item.owner, item.run_id)
        assert slot is not None
        control.register(slot, item)
    assert control.reserve("tenant", "issuer|alice", "overflow") is None
    commits = []

    def committed(connection):
        commits.append(connection)

    event.listen(engine, "commit", committed)
    try:
        await control.renew()
        event.remove(engine, "commit", committed)
        assert len(commits) == 2
        async with primary_authority(fresh=True):
            session = worker.mappings.controls._require_session()
            jobs = (
                await session.execute(
                    select(Job.id, Job.lease_until, Job.attempts).where(
                        Job.id.in_([item.job_id for item in current])
                    )
                )
            ).all()
            assert len(jobs) == 64
            assert all(
                row.lease_until > original_expiry + timedelta(seconds=120) and row.attempts == first.attempt
                for row in jobs
            )
    finally:
        if event.contains(engine, "commit", committed):
            event.remove(engine, "commit", committed)
        await control.close()
