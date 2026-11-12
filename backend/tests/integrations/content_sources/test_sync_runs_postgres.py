# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pyfly.kernel import ConflictException
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import source_database as source_database
from test_sync_intake_postgres import bind
from test_sync_intake_postgres import intake as intake

from koinon.integrations.content_sources.mapping_entities import SourceObject
from koinon.integrations.content_sources.sync_controls import SourceControlRepository, SyncAuthorityCapture
from koinon.integrations.content_sources.sync_dtos import SourceControlInput
from koinon.integrations.content_sources.sync_entities import (
    SourceMappingPolicy,
    SourceSyncRun,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_runs import SourceRunRepository
from koinon.jobs.entities import Job

pytestmark = pytest.mark.integration


async def test_source_job_lease_takeover_fences_old_worker_and_keeps_run_identity(intake):
    now = datetime.now(UTC) + timedelta(seconds=1)
    async with intake.sessions.begin() as session:
        job = await session.get(Job, "source-run")
        job.status, job.worker_id, job.lease_until = "queued", None, None
    async with intake.sessions.begin() as session:
        first = await SourceRunRepository(session=session).claim(
            "retained", "issuer|alice", "run", "one", at=now
        )
    assert first is not None and first.attempt == 1
    async with intake.sessions.begin() as session:
        assert (
            await SourceRunRepository(session=session).claim("retained", "issuer|alice", "run", "two", at=now)
            is None
        )
    async with intake.sessions.begin() as session:
        second = await SourceRunRepository(session=session).claim(
            "retained", "issuer|alice", "run", "two", at=now + timedelta(seconds=121)
        )
    assert second is not None and second.attempt == 2 and second.run_id == first.run_id
    async with intake.sessions.begin() as session:
        records = SourceRunRepository(session=session)
        with pytest.raises(ConflictException):
            await records.fenced(first, at=now + timedelta(seconds=122))
        await records.fenced(second, at=now + timedelta(seconds=122))
        assert (await session.get(SourceSyncRun, "run")).status == "reconciling"


async def test_source_lease_owner_and_expiry_are_required(intake):
    now = datetime.now(UTC) + timedelta(minutes=2)
    async with intake.sessions.begin() as session:
        records = SourceRunRepository(session=session)
        with pytest.raises(ConflictException):
            await records.claim("retained", "issuer|bob", "run", "intruder", at=now)
        lease = await records.claim("retained", "issuer|alice", "run", "worker", at=now)
    async with intake.sessions.begin() as session:
        with pytest.raises(ConflictException):
            await SourceRunRepository(session=session).fenced(lease, at=now + timedelta(seconds=121))


async def execution(intake):
    now = datetime.now(UTC) + timedelta(minutes=2)
    async with intake.sessions.begin() as session:
        lease = await SourceRunRepository(session=session).claim(
            "retained", "issuer|alice", "run", "finish", at=now
        )
        policy = await session.get(SourceMappingPolicy, "accepted")
        capture = SyncAuthorityCapture(2, policy.authority_sha256, policy.id, policy.policy_sha256)
    return lease, capture, now


async def test_cancel_settles_unstarted_work_and_job_without_claiming_scan_completion(intake):
    lease, _, now = await execution(intake)
    async with intake.sessions.begin() as session:
        await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            "mapping",
            "cancel",
            SourceControlInput(operation_id=str(uuid4()), expected_revision=1),
            target_run_id="run",
        )
    async with intake.sessions.begin() as session:
        assert await SourceRunRepository(session=session).finish(lease, at=now)
    async with intake.sessions() as session:
        run = await session.get(SourceSyncRun, "run")
        job = await session.get(Job, "source-run")
        state = await session.get(SourceSyncState, "mapping")
        assert run.status == "cancelled" and not run.enumeration_complete
        assert job.status == "cancelled" and job.worker_id is None and job.lease_until is None
        assert (await session.get(SourceSyncWork, "work")).status == "removed"
        assert state.last_complete_scan_generation == 0 and state.enabled


async def test_unknown_native_attempt_keeps_cancelled_run_reconciling(intake):
    await bind(intake)
    lease, _, now = await execution(intake)
    async with intake.sessions.begin() as session:
        await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            "mapping",
            "cancel",
            SourceControlInput(operation_id=str(uuid4()), expected_revision=1),
            target_run_id="run",
        )
    async with intake.sessions.begin() as session:
        assert not await SourceRunRepository(session=session).finish(lease, at=now)
    async with intake.sessions() as session:
        assert (await session.get(SourceSyncRun, "run")).status == "reconciling"
        assert (await session.get(SourceSyncWork, "work")).status == "processing"
        assert (await session.get(Job, "source-run")).status == "running"


async def test_only_complete_fresh_scan_retires_missing_objects_and_promotes_checkpoint(intake):
    lease, capture, now = await execution(intake)
    async with intake.sessions.begin() as session:
        (await session.get(SourceSyncWork, "work")).status = "skipped"
        session.add(
            SourceObject(
                id="missing",
                tenant_id="retained",
                mapping_id="mapping",
                item_id="missing",
                generation=1,
                mapping_revision=1,
                remote_version="old",
                state="pending",
            )
        )
    async with intake.sessions.begin() as session:
        assert not await SourceRunRepository(session=session).finish(lease, capture=capture, at=now)
    async with intake.sessions.begin() as session:
        assert (await session.get(SourceObject, "missing")).generation == 1
        (await session.get(SourceSyncRun, "run")).enumeration_complete = True
    async with intake.sessions.begin() as session:
        assert await SourceRunRepository(session=session).finish(lease, capture=capture, at=now)
    async with intake.sessions() as session:
        origin = await session.get(SourceObject, "missing")
        assert (origin.state, origin.generation) == ("removed", 2)
        assert (await session.get(SourceSyncState, "mapping")).last_complete_scan_generation == 1
        assert (await session.get(SourceSyncRun, "run")).status == "succeeded"
        assert (await session.get(Job, "source-run")).status == "succeeded"
