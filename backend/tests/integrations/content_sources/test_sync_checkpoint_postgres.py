# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta

import psycopg
import pytest
import test_sync_intake_postgres as intake_fixture
from pyfly.kernel import ConflictException
from sqlalchemy import select
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database

from koinon.catalog.entities import CatalogEntry
from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
from koinon.integrations.content_sources.import_entities import SourceImportAttempt
from koinon.integrations.content_sources.mapping_entities import SourceObject
from koinon.integrations.content_sources.sync_checkpoints import SourceCheckpoints
from koinon.integrations.content_sources.sync_entities import (
    SourceImportedVersion,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_intake import SourceSyncIntake
from koinon.integrations.content_sources.sync_runs import SourceRunRepository
from koinon.integrations.content_sources.sync_walk import WalkItem, WalkPage
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem
from koinon.knowledge.bulk.ports import NativeCommit

pytestmark = pytest.mark.integration


@pytest.fixture
async def intake(source_sessions, source_database, request, monkeypatch):
    if getattr(request, "param", None) == "file":
        review = intake_fixture.MappingReviewInput

        def selected_file(**values):
            return review(**{**values, "recursive": False})

        monkeypatch.setattr(intake_fixture, "MappingReviewInput", selected_file)
    value = await intake_fixture.intake.__wrapped__(source_sessions, source_database)
    _, role, _ = source_database
    with psycopg.connect(value.uri) as connection:
        for table in (
            "lattice_domain_bindings",
            "koinon_content_publication_baselines",
            "koinon_content_publication_targets",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
    async with value.sessions.begin() as session:
        state = await session.get(SourceSyncState, "mapping")
        state.scan_max_items, state.scan_observed_count = 100, 1
        state.revision += 1
    return value


async def bind_new_targets(intake):
    """Reserve actual new targets in the transaction that records their initial provenance."""
    async with intake.sessions.begin() as session:
        guard = SourceSyncIntake(session=session)
        await guard.admit(intake.admission)
        for identifier, kind, parent in (
            ("reserved-source", "source", "folder"),
            ("reserved-asset", "document", "reserved-source"),
        ):
            session.add(
                CatalogEntry(
                    id=identifier,
                    tenant_id="retained",
                    kind=kind,
                    name=identifier,
                    workspace_id="workspace",
                    project_id="project",
                    parent_id=parent,
                    status="pending",
                    created_by="issuer|alice",
                )
            )
            await session.flush()
        session.add(
            BulkBatch(
                id="reserved-batch",
                tenant_id="retained",
                subject="issuer|alice",
                workspace_id="workspace",
                project_id="project",
                parent_id="folder",
                key_hash="4" * 64,
                request_hash="5" * 64,
                request_json={"_source_admission": asdict(intake.admission)},
                total_bytes=7,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        await session.flush()
        item = BulkItem(
            id="reserved-item",
            batch_id="reserved-batch",
            ordinal=0,
            client_item_id="remote-file",
            filename="report.txt",
            mode="document",
            size_bytes=7,
            sha256="d" * 64,
            source_id="reserved-source",
            asset_id="reserved-asset",
        )
        session.add(item)
        await session.flush()
        await guard.bind(intake.admission, 0, item)
    intake.lease.item_id, intake.lease.batch_id = "reserved-item", "reserved-batch"
    intake.lease.source_id, intake.lease.asset_id = "reserved-source", "reserved-asset"


def page():
    scope = SourceScope(Account("google_drive", "provider-alice"), "drive")
    item = RemoteItem(scope, "new-file", "new.txt", "file", "v1", 7, "text/plain", ("root",))
    return WalkPage((WalkItem(item, ("root",)),), {"encrypted_by_caller": True}, False, 1)


async def lease(intake):
    now = datetime.now(UTC) + timedelta(minutes=2)
    async with intake.sessions.begin() as session:
        result = await SourceRunRepository(session=session).claim(
            "retained", "issuer|alice", "run", "checkpoint", at=now
        )
    return result, now


async def test_page_observations_and_cursor_commit_once_and_replay_after_lost_response(intake):
    execution, now = await lease(intake)
    async with intake.sessions.begin() as session:
        first = await SourceCheckpoints(session=session).append(
            execution, 1, page(), cursor_ciphertext=b"encrypted", at=now
        )
    async with intake.sessions.begin() as session:
        replay = await SourceCheckpoints(session=session).append(
            execution, 1, page(), cursor_ciphertext=b"encrypted", at=now
        )
        assert replay == first and len(first) == 1
    async with intake.sessions() as session:
        run = await session.get(SourceSyncRun, "run")
        observations = list(
            (
                await session.scalars(
                    select(SourceSyncObservation).where(SourceSyncObservation.page_sequence == 2)
                )
            ).all()
        )
        assert (run.page_sequence, run.cursor_ciphertext, run.enumeration_complete) == (
            2,
            b"encrypted",
            False,
        )
        assert len(observations) == 1 and observations[0].id == first[0].observation_id


async def test_page_rollback_never_leaves_objects_without_checkpoint(intake):
    execution, now = await lease(intake)
    with pytest.raises(RuntimeError, match="crash"):
        async with intake.sessions.begin() as session:
            await SourceCheckpoints(session=session).append(
                execution, 1, page(), cursor_ciphertext=b"encrypted", at=now
            )
            raise RuntimeError("crash")
    async with intake.sessions() as session:
        assert (await session.get(SourceSyncRun, "run")).page_sequence == 1
        assert (await session.get(SourceSyncState, "mapping")).scan_observed_count == 1
        assert await session.scalar(select(SourceObject).where(SourceObject.item_id == "new-file")) is None


@pytest.mark.parametrize("intake", ["file"], indirect=True)
async def test_selected_file_checkpoint_preserves_actual_parent_and_empty_ancestry(intake):
    execution, now = await lease(intake)
    selected = replace(page().items[0].item, item_id="root", parents=("actual-parent",))
    singleton = WalkPage((WalkItem(selected, ()),), None, True, 1)
    async with intake.sessions.begin() as session:
        pins = await SourceCheckpoints(session=session).append(
            execution, 1, singleton, cursor_ciphertext=None, at=now
        )
    async with intake.sessions() as session:
        origin = await session.get(SourceObject, pins[0].object_id)
        observation = await session.get(SourceSyncObservation, pins[0].observation_id)
        assert (origin.item_id, origin.remote_parent_id, origin.remote_name, origin.remote_ancestry_json) == (
            "root",
            "actual-parent",
            "new.txt",
            [],
        )
        assert observation.event_json["ancestry"] == []
        assert observation.event_json["item"]["parents"] == ["actual-parent"]
        assert (await session.get(SourceSyncRun, "run")).enumeration_complete


@pytest.mark.parametrize("intake", ["file"], indirect=True)
@pytest.mark.parametrize("invalid", ["synthetic_ancestry", "foreign", "folder", "multiple", "parents"])
async def test_selected_file_checkpoint_rejects_invalid_root_observations(intake, invalid):
    execution, now = await lease(intake)
    item = replace(page().items[0].item, item_id="root", parents=("actual-parent",))
    ancestry = ()
    if invalid == "synthetic_ancestry":
        ancestry, item = ("root",), replace(item, parents=("root",))
    elif invalid == "foreign":
        item = replace(item, item_id="foreign")
    elif invalid == "folder":
        item = replace(item, kind="folder")
    elif invalid == "parents":
        item = replace(item, parents=("one", "two"))
    entries = (WalkItem(item, ancestry),)
    if invalid == "multiple":
        entries += (WalkItem(replace(item, item_id="other"), ()),)
    async with intake.sessions.begin() as session:
        with pytest.raises(ConflictException) as failure:
            await SourceCheckpoints(session=session).append(
                execution, 1, WalkPage(entries, None, True, len(entries)), cursor_ciphertext=None, at=now
            )
        assert failure.value.code == "SOURCE_LEASE_LOST"
        assert (await session.get(SourceSyncState, "mapping")).scan_observed_count == 1


async def test_raw_count_includes_filtered_records_once_across_checkpoint_replay(intake):
    execution, now = await lease(intake)
    observed = replace(page(), raw_observed_count=99)
    async with intake.sessions.begin() as session:
        first = await SourceCheckpoints(session=session).append(
            execution, 1, observed, cursor_ciphertext=b"next", at=now
        )
    async with intake.sessions.begin() as session:
        replay = await SourceCheckpoints(session=session).append(
            execution, 1, observed, cursor_ciphertext=b"next", at=now
        )
        assert replay == first
        assert (await session.get(SourceSyncState, "mapping")).scan_observed_count == 100
    async with intake.sessions.begin() as session:
        with pytest.raises(ConflictException):
            await SourceCheckpoints(session=session).append(
                execution, 1, replace(observed, raw_observed_count=98), cursor_ciphertext=b"next", at=now
            )
    async with intake.sessions.begin() as session:
        await SourceCheckpoints(session=session).append(
            execution, 2, WalkPage((), None, True, 0), cursor_ciphertext=None, at=now
        )
        assert (await session.get(SourceSyncRun, "run")).enumeration_complete
        assert (await session.get(SourceSyncState, "mapping")).scan_observed_count == 100


async def test_over_limit_page_never_promotes_completion_or_admits_its_objects(intake):
    execution, now = await lease(intake)
    observed = replace(page(), raw_observed_count=100, complete=True, next_state=None)
    async with intake.sessions.begin() as session:
        pins = await SourceCheckpoints(session=session).append(
            execution, 1, observed, cursor_ciphertext=None, at=now
        )
        assert pins == ()
    async with intake.sessions() as session:
        state = await session.get(SourceSyncState, "mapping")
        run = await session.get(SourceSyncRun, "run")
        assert state.scan_observed_count == 101
        assert state.last_complete_scan_generation == 0
        assert not run.enumeration_complete and run.page_sequence == 1
        assert run.counters_json["error_code"] == "SOURCE_SCAN_LIMIT_EXCEEDED"
        assert await session.scalar(select(SourceObject).where(SourceObject.item_id == "new-file")) is None
    async with intake.sessions.begin() as session:
        assert (
            await SourceCheckpoints(session=session).append(
                execution, 1, observed, cursor_ciphertext=None, at=now
            )
            == ()
        )
        assert (await session.get(SourceSyncState, "mapping")).scan_observed_count == 101


@pytest.mark.parametrize("state", ["pending", "failed"])
async def test_same_version_observation_retains_settled_attempt_without_reusing_old_admission(intake, state):
    await bind_new_targets(intake)
    receipt = NativeCommit(
        "canon",
        "native-space",
        "native-source",
        "native-asset",
        "d" * 64,
        7,
        source_version_id="native-version",
        extraction_id="extraction",
    )
    async with intake.sessions.begin() as session:
        await SourceSyncIntake(session=session).settle(intake.lease, receipt)
        origin = await session.get(SourceObject, "origin")
        origin.state, origin.remote_kind = state, "file"
        attempt_id = (await session.get(SourceSyncWork, "work")).attempt_id
    execution, now = await lease(intake)
    observed = page()
    observed = replace(
        observed,
        items=(replace(observed.items[0], item=replace(observed.items[0].item, item_id="remote-file")),),
    )
    async with intake.sessions.begin() as session:
        pins = await SourceCheckpoints(session=session).append(
            execution, 1, observed, cursor_ciphertext=b"next", at=now
        )
    async with intake.sessions.begin() as session:
        origin = await session.get(SourceObject, "origin")
        work = await session.get(SourceSyncWork, "work")
        attempt = await session.get(SourceImportAttempt, attempt_id)
        assert (origin.generation, origin.state, origin.published_native_version_id) == (1, "pending", None)
        assert pins[0].work_id == work.id and work.attempt_id == attempt.id
        assert work.status == "conflict" and attempt.receipt_json is not None
        assert work.error_code == "SOURCE_PUBLICATION_NOT_ACKNOWLEDGED"
        assert list((await session.scalars(select(SourceImportedVersion))).all()) == []
        guard = SourceSyncIntake(session=session)
        with pytest.raises(ConflictException):
            await guard._fence(intake.admission)
        await guard._fence(replace(intake.admission, items=pins))


@pytest.mark.parametrize(
    "state,version",
    [
        ("pending", "v2"),
        ("removed", "v1"),
        ("excluded", "v1"),
    ],
)
async def test_version_change_or_resurrection_allocates_a_new_generation(intake, state, version):
    async with intake.sessions.begin() as session:
        origin = await session.get(SourceObject, "origin")
        origin.state = state
    execution, now = await lease(intake)
    observed = page()
    observed = replace(
        observed,
        items=(
            replace(
                observed.items[0],
                item=replace(observed.items[0].item, item_id="remote-file", version=version),
            ),
        ),
    )
    async with intake.sessions.begin() as session:
        pins = await SourceCheckpoints(session=session).append(
            execution, 1, observed, cursor_ciphertext=b"next", at=now
        )
        assert pins[0].generation == 2 and pins[0].work_id != "work"
