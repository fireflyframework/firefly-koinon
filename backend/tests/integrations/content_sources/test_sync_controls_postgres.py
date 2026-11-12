# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Control effects and replay receipts share a transaction on real PostgreSQL."""

import asyncio
from uuid import uuid4

import psycopg
import pytest
from sqlalchemy import select
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import job_and_run, policy, state

from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.sync_controls import SourceControlRepository
from koinon.integrations.content_sources.sync_dtos import SourceControlInput
from koinon.integrations.content_sources.sync_entities import (
    SourceControlOperation,
    SourceSyncRun,
    SourceSyncState,
)
from koinon.jobs.errors import JobConflict

pytestmark = pytest.mark.integration


@pytest.fixture
async def control_state(source_sessions, source_database):
    sessions, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        for table in (
            "lattice_jobs",
            "koinon_content_sync_states",
            "koinon_content_sync_runs",
            "koinon_content_policies",
            "koinon_content_control_operations",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
    return sessions, uri


def command(revision=1, operation=None):
    return SourceControlInput(expected_revision=revision, operation_id=operation or str(uuid4()))


async def apply(sessions, action, request, *, target=None, actor="issuer|alice"):
    async with sessions.begin() as session:
        return await SourceControlRepository(session=session).apply(
            "retained", actor, "mapping", action, request, target_run_id=target
        )


async def test_pause_replay_after_restart_returns_original_receipt_without_policy_churn(control_state):
    sessions, _ = control_state
    request = command()
    first = await apply(sessions, "pause", request)
    assert first.disposition == "paused" and first.control_revision == 2
    assert await apply(sessions, "pause", request) == first
    async with sessions() as session:
        mapping = await session.get(SourceMapping, "mapping")
        current = await session.get(SourceSyncState, "mapping")
        receipts = list((await session.scalars(select(SourceControlOperation))).all())
        assert (mapping.status, mapping.revision, current.enabled, current.revision) == (
            "paused",
            1,
            False,
            2,
        )
        assert len(receipts) == 1


async def test_same_operation_cannot_change_action_expected_revision_or_owner(control_state):
    sessions, _ = control_state
    request = command()
    await apply(sessions, "pause", request)
    for action, changed, actor in (
        ("retire", request, "issuer|alice"),
        ("pause", command(2, request.operation_id), "issuer|alice"),
        ("pause", request, "issuer|bob"),
    ):
        with pytest.raises(JobConflict):
            await apply(sessions, action, changed, actor=actor)
    async with sessions() as session:
        assert (await session.get(SourceMapping, "mapping")).status == "paused"


async def test_rollback_between_effect_and_receipt_leaves_neither(control_state):
    sessions, _ = control_state
    with pytest.raises(RuntimeError, match="lost transaction"):
        async with sessions.begin() as session:
            await SourceControlRepository(session=session).apply(
                "retained", "issuer|alice", "mapping", "pause", command()
            )
            raise RuntimeError("lost transaction")
    async with sessions() as session:
        assert (await session.get(SourceMapping, "mapping")).status == "active"
        assert (await session.get(SourceSyncState, "mapping")).revision == 1
        assert list((await session.scalars(select(SourceControlOperation))).all()) == []


async def test_cancel_marks_run_without_revoking_committed_generations_or_schedule(control_state):
    sessions, uri = control_state
    with psycopg.connect(uri) as connection:
        job_and_run(connection, "running")
        previous = connection.execute("SELECT next_run_at FROM koinon_content_sync_states").fetchone()[0]
    result = await apply(sessions, "cancel", command(), target="running")
    assert result.disposition == "stopping"
    async with sessions() as session:
        run = await session.get(SourceSyncRun, "running")
        current = await session.get(SourceSyncState, "mapping")
        assert run.status == "queued" and run.cancel_operation_id == result.receipt_id
        assert (await session.get(SourceObject, "origin")).generation == 1
        assert current.enabled and current.next_run_at == previous


async def test_retire_invalidates_objects_and_requests_cancellation_atomically(control_state):
    sessions, uri = control_state
    with psycopg.connect(uri) as connection:
        job_and_run(connection, "running")
    result = await apply(sessions, "retire", command())
    async with sessions() as session:
        mapping = await session.get(SourceMapping, "mapping")
        origin = await session.get(SourceObject, "origin")
        run = await session.get(SourceSyncRun, "running")
        assert (mapping.status, mapping.revision, origin.state, origin.generation) == (
            "retired",
            1,
            "excluded",
            2,
        )
        assert run.cancel_operation_id == result.receipt_id


async def test_duplicate_transition_with_new_uuid_conflicts_without_second_receipt(control_state):
    sessions, _ = control_state
    await apply(sessions, "pause", command())
    with pytest.raises(JobConflict):
        await apply(sessions, "pause", command(2))
    async with sessions() as session:
        assert len(list((await session.scalars(select(SourceControlOperation))).all())) == 1


async def test_opposing_commands_share_one_control_revision(control_state):
    sessions, _ = control_state
    results = await asyncio.gather(
        apply(sessions, "pause", command()), apply(sessions, "retire", command()), return_exceptions=True
    )
    assert sum(isinstance(result, JobConflict) for result in results) == 1
    async with sessions() as session:
        assert (await session.get(SourceSyncState, "mapping")).revision == 2
        assert len(list((await session.scalars(select(SourceControlOperation))).all())) == 1


async def test_replay_after_later_command_returns_original_disposition(control_state):
    sessions, _ = control_state
    request = command()
    paused = await apply(sessions, "pause", request)
    await apply(sessions, "retire", command(2))
    assert await apply(sessions, "pause", request) == paused
    async with sessions() as session:
        assert (await session.get(SourceSyncState, "mapping")).revision == 3


async def test_resume_without_fresh_provider_capture_keeps_mapping_paused(control_state):
    sessions, _ = control_state
    await apply(sessions, "pause", command())
    with pytest.raises(JobConflict):
        await apply(sessions, "resume", command(2))
    async with sessions() as session:
        assert (await session.get(SourceMapping, "mapping")).status == "paused"
        assert (await session.get(SourceSyncState, "mapping")).revision == 2
