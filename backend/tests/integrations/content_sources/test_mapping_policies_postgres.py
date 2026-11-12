# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Policy review revisions do not become authority until exact human apply."""

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import select
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database

from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.mapping_dtos import IntervalSchedule
from koinon.integrations.content_sources.mapping_entities import SourceMapping
from koinon.integrations.content_sources.mapping_policies import PolicyCapture, SourcePolicyRepository
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.sync_controls import SourceControlRepository, SyncAuthorityCapture
from koinon.integrations.content_sources.sync_dtos import (
    SourceControlInput,
    SourcePolicyApplyInput,
    SourcePolicyReviewInput,
)
from koinon.integrations.content_sources.sync_entities import (
    SourceMappingPolicy,
    SourcePolicyOperation,
    SourceSyncRun,
    SourceSyncState,
)
from koinon.jobs.entities import Job
from koinon.jobs.errors import JobConflict

pytestmark = pytest.mark.integration


@pytest.fixture
async def policies(source_sessions, source_database):
    sessions, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        for table in (
            "koinon_content_policies",
            "koinon_content_policy_operations",
            "koinon_content_sync_states",
            "koinon_content_sync_runs",
            "koinon_content_control_operations",
            "lattice_jobs",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
    async with sessions.begin() as session:
        connection = await session.get(PersonalSourceConnection, "connection")
        connection.config_fingerprint = "a" * 64
        authority, digest = source_authority(connection)
    now = datetime.now(UTC)
    capture = PolicyCapture(
        1, authority, digest, ("root",), "b" * 64, True, 0, now, now + timedelta(minutes=15)
    )
    return sessions, capture


def review_request():
    return SourcePolicyReviewInput(
        operation_id=str(uuid4()),
        connection_id="connection",
        drive_id="drive",
        root_id="root",
        recursive=True,
        removal_policy="retire",
        destination={"workspace_id": "workspace", "project_id": "project", "parent_id": "folder"},
    )


async def prepare(policies, request, *, mapping=None, expected=None):
    sessions, capture = policies
    async with sessions.begin() as session:
        return await SourcePolicyRepository(session=session).review(
            "retained",
            "issuer|alice",
            request,
            "d" * 64,
            capture,
            mapping_id=mapping,
            expected_revision=expected,
        )


async def accept(policies, result, *, session_hash="d" * 64, operation=None, at=None):
    sessions, capture = policies
    request = SourcePolicyApplyInput(
        operation_id=operation or str(uuid4()),
        expected_revision=result.result_policy_revision,
        review_id=result.policy_id,
        review_digest=result.review_digest,
    )
    async with sessions.begin() as session:
        return await SourcePolicyRepository(session=session).apply(
            "retained", "issuer|alice", result.mapping_id, request, session_hash, capture, at=at
        )


async def test_initial_review_replay_is_retained_without_accepted_state(policies):
    request = review_request()
    result = await prepare(policies, request)
    assert result.expected_policy_revision is None and result.result_policy_revision == 1
    assert await prepare(policies, request) == result
    sessions, _ = policies
    async with sessions() as session:
        assert await session.get(SourceSyncState, result.mapping_id) is None
        assert len(list((await session.scalars(select(SourcePolicyOperation))).all())) == 1


@pytest.mark.parametrize("hierarchy", ["preserve", "flatten"])
async def test_partial_review_never_activates_a_mapping(policies, hierarchy):
    sessions, capture = policies
    partial = (sessions, replace(capture, preview_complete=False))
    request = review_request().model_copy(update={"hierarchy": hierarchy})
    reviewed = await prepare(partial, request)
    with pytest.raises(JobConflict):
        await accept(partial, reviewed)
    async with sessions() as session:
        assert (await session.get(SourceMapping, reviewed.mapping_id)).status == "reviewed"
        assert await session.get(SourceSyncState, reviewed.mapping_id) is None
        assert (await session.get(SourceMappingPolicy, reviewed.policy_id)).accepted_at is None


async def test_abandoned_reviews_preserve_accepted_revision_and_superseded_apply_fails(policies):
    initial = await prepare(policies, review_request())
    await accept(policies, initial)
    second = await prepare(policies, review_request(), mapping=initial.mapping_id, expected=1)
    third = await prepare(policies, review_request(), mapping=initial.mapping_id, expected=2)
    sessions, _ = policies
    async with sessions() as session:
        mapping = await session.get(SourceMapping, initial.mapping_id)
        state = await session.get(SourceSyncState, initial.mapping_id)
        assert mapping.revision == 1 and state.accepted_policy_id == initial.policy_id and state.enabled
    with pytest.raises(JobConflict):
        await accept(policies, second)
    await accept(policies, third)
    async with sessions() as session:
        assert (await session.get(SourceMapping, initial.mapping_id)).revision == 3
        assert (await session.get(SourceSyncState, initial.mapping_id)).accepted_policy_id == third.policy_id


async def test_apply_receipt_replays_and_cross_action_uuid_is_rejected(policies):
    request = review_request()
    reviewed = await prepare(policies, request)
    with pytest.raises(JobConflict):
        await accept(policies, reviewed, operation=request.operation_id)
    operation = str(uuid4())
    result = await accept(policies, reviewed, operation=operation)
    assert await accept(policies, reviewed, operation=operation) == result


async def test_review_cas_and_exact_human_session_and_expiry_are_required(policies):
    initial = await prepare(policies, review_request())
    with pytest.raises(JobConflict):
        await prepare(policies, review_request(), mapping=initial.mapping_id, expected=7)
    with pytest.raises(JobConflict):
        await accept(policies, initial, session_hash="e" * 64)
    with pytest.raises(JobConflict):
        await accept(policies, initial, at=initial.review_expires_at)
    sessions, _ = policies
    async with sessions() as session:
        assert (await session.get(SourceMappingPolicy, initial.policy_id)).accepted_at is None


async def test_rollback_after_acceptance_rolls_back_state_policy_and_receipt(policies):
    reviewed = await prepare(policies, review_request())
    sessions, capture = policies
    request = SourcePolicyApplyInput(
        operation_id=str(uuid4()),
        expected_revision=1,
        review_id=reviewed.policy_id,
        review_digest=reviewed.review_digest,
    )
    with pytest.raises(RuntimeError):
        async with sessions.begin() as session:
            await SourcePolicyRepository(session=session).apply(
                "retained", "issuer|alice", reviewed.mapping_id, request, "d" * 64, capture
            )
            raise RuntimeError("lost commit")
    async with sessions() as session:
        assert await session.get(SourceSyncState, reviewed.mapping_id) is None
        assert (await session.get(SourceMappingPolicy, reviewed.policy_id)).accepted_at is None
        assert len(list((await session.scalars(select(SourcePolicyOperation))).all())) == 1


async def test_competing_reviews_have_one_winner_without_advancing_accepted_authority(policies):
    reviewed = await prepare(policies, review_request())
    await accept(policies, reviewed)
    results = await asyncio.gather(
        prepare(policies, review_request(), mapping=reviewed.mapping_id, expected=1),
        prepare(policies, review_request(), mapping=reviewed.mapping_id, expected=1),
        return_exceptions=True,
    )
    assert sum(isinstance(result, JobConflict) for result in results) == 1
    sessions, _ = policies
    async with sessions() as session:
        assert (await session.get(SourceMapping, reviewed.mapping_id)).revision == 1
        assert len(list((await session.scalars(select(SourceMappingPolicy))).all())) == 2


async def test_changed_preview_or_connection_cannot_apply_human_review(policies):
    reviewed = await prepare(policies, review_request())
    sessions, capture = policies
    for changed in (replace(capture, preview_sha256="f" * 64), replace(capture, connection_revision=2)):
        with pytest.raises(JobConflict):
            await accept((sessions, changed), reviewed)
    async with sessions() as session:
        assert await session.get(SourceSyncState, reviewed.mapping_id) is None


async def test_scheduled_occurrence_is_atomic_unique_and_coalesces_missed_intervals(policies):
    request = review_request().model_copy(update={"schedule": IntervalSchedule(kind="interval", seconds=900)})
    reviewed = await prepare(policies, request)
    await accept(policies, reviewed)
    sessions, captured = policies
    now = datetime.now(UTC)
    due = now - timedelta(seconds=1900)
    async with sessions.begin() as session:
        scheduled = await session.get(SourceSyncState, reviewed.mapping_id)
        scheduled.next_run_at, scheduled.revision = due, 2
        policy = await session.get(SourceMappingPolicy, reviewed.policy_id)
        capture = SyncAuthorityCapture(1, captured.authority_sha256, policy.id, policy.policy_sha256)
    command = SourceControlInput(operation_id=str(uuid4()), expected_revision=2)
    async with sessions.begin() as session:
        result = await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            reviewed.mapping_id,
            "sync",
            command,
            capture=capture,
            at=now,
            _occurrence=due,
        )
    async with sessions.begin() as session:
        assert (
            await SourceControlRepository(session=session).apply(
                "retained",
                "issuer|alice",
                reviewed.mapping_id,
                "sync",
                command,
                capture=capture,
                at=now,
                _occurrence=due,
            )
            == result
        )
        run = await session.get(SourceSyncRun, result.run_id)
        state = await session.get(SourceSyncState, reviewed.mapping_id)
        assert run.trigger_kind == "interval" and run.occurrence_key == policy.id + ":" + due.isoformat()
        assert state.next_run_at == due + timedelta(seconds=2700)
        assert len(list((await session.scalars(select(Job))).all())) == 1
