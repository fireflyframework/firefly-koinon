# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private intake identity and source publication races on migrated PostgreSQL."""

import asyncio
from dataclasses import asdict, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import psycopg
import pytest
from pyfly.kernel import ConflictException
from sqlalchemy import select
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database

from koinon.catalog.entities import CatalogEntry
from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.sync_controls import SourceControlRepository, SyncAuthorityCapture
from koinon.integrations.content_sources.sync_dtos import SourceControlInput
from koinon.integrations.content_sources.sync_entities import (
    SourceImportedAsset,
    SourceImportedVersion,
    SourceMappingPolicy,
    SourcePolicyOperation,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.integrations.content_sources.sync_intake import SourceSyncIntake
from koinon.jobs.entities import Job
from koinon.jobs.errors import JobConflict
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem
from koinon.knowledge.bulk.ports import NativeCommit, SourceIntakeAdmission, SourceIntakeItem

pytestmark = pytest.mark.integration


@pytest.fixture
async def intake(source_sessions, source_database):
    sessions, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        for table in (
            "lattice_jobs",
            "lattice_domain_bindings",
            "lattice_memberships",
            "koinon_content_policies",
            "koinon_content_sync_states",
            "koinon_content_sync_runs",
            "koinon_content_sync_work",
            "koinon_content_sync_observations",
            "koinon_content_folder_bindings",
            "koinon_content_folder_publications",
            "koinon_content_imported_assets",
            "koinon_content_imported_versions",
            "koinon_content_control_operations",
            "koinon_content_policy_operations",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
    admission = SourceIntakeAdmission(
        "retained",
        "issuer|alice",
        "mapping",
        1,
        2,
        "run",
        ("workspace", "project", "folder"),
        (SourceIntakeItem("origin", 1, "v1", "initial-observation", "work", 1, 0, "f" * 64),),
    )
    async with sessions.begin() as session:
        connection = await session.get(PersonalSourceConnection, "connection")
        connection.config_fingerprint, connection.revision = "a" * 64, 2
        mapping = await session.get(SourceMapping, "mapping")
        mapping.config_fingerprint = connection.config_fingerprint
        authority, digest = source_authority(connection)
        request = MappingReviewInput(
            connection_id="connection",
            drive_id="drive",
            root_id="root",
            recursive=True,
            removal_policy="retire",
            destination={"workspace_id": "workspace", "project_id": "project", "parent_id": "folder"},
        )
        now = datetime.now(UTC)
        operation, receipt = str(uuid4()), str(uuid4())
        session.add(
            SourceMappingPolicy(
                id="accepted",
                tenant_id="retained",
                owner="issuer|alice",
                mapping_id="mapping",
                revision=1,
                mapping_revision=1,
                authority_sha256=digest,
                policy_json={"authority": authority, "request": request.model_dump(mode="json")},
                policy_sha256="b" * 64,
                root_ancestry_json=["root"],
                review_id="review",
                review_digest="c" * 64,
                review_expires_at=now + timedelta(days=1),
                accepted_by="issuer|alice",
                accepted_session_hash="d" * 64,
                accepted_operation_id=operation,
                accepted_at=now,
            )
        )
        await session.flush()
        session.add(
            SourcePolicyOperation(
                id=receipt,
                tenant_id="retained",
                owner="issuer|alice",
                operation_id=operation,
                action="apply",
                mapping_id="mapping",
                policy_id="accepted",
                expected_policy_revision=1,
                result_policy_revision=1,
                payload_sha256="e" * 64,
                result_json=dict(
                    schema="koinon.source-policy-operation.v1",
                    receipt_id=receipt,
                    operation_id=operation,
                    action="apply",
                    mapping_id="mapping",
                    policy_id="accepted",
                    expected_policy_revision=1,
                    result_policy_revision=1,
                    review_digest="c" * 64,
                    review_expires_at=(now + timedelta(days=1)).isoformat(),
                    disposition="accepted",
                ),
            )
        )
        await session.flush()
        session.add(
            SourceSyncState(
                mapping_id="mapping",
                tenant_id="retained",
                accepted_policy_id="accepted",
                enabled=True,
                revision=1,
                next_run_at=None,
                cursor_ciphertext=None,
                scan_generation=1,
            )
        )
        session.add(
            Job(
                id="source-run",
                tenant_id="retained",
                resource_id="mapping",
                kind="content.source.reconcile",
                idempotency_key="source-run",
                payload_hash="e" * 64,
                payload={},
                status="running",
                worker_id="worker",
                lease_until=now + timedelta(minutes=1),
            )
        )
        await session.flush()
        session.add(
            SourceSyncRun(
                id="run",
                tenant_id="retained",
                mapping_id="mapping",
                policy_id="accepted",
                mapping_revision=1,
                connection_revision=2,
                job_id="source-run",
                trigger_kind="manual",
                operation_id=str(uuid4()),
                payload_sha256="e" * 64,
                occurrence_key=None,
                status="running",
                cursor_ciphertext=None,
                scan_generation=1,
                finished_at=None,
            )
        )
        session.add(
            SourceSyncWork(
                id="work",
                tenant_id="retained",
                mapping_id="mapping",
                object_id="origin",
                generation=1,
                remote_version="v1",
                event_sha256="f" * 64,
                status="admitted",
                error_code=None,
                attempt_id=None,
                expected_local_revision=None,
                expected_sha256=None,
            )
        )
        session.add(
            BulkBatch(
                id="source-batch",
                tenant_id="retained",
                subject="issuer|alice",
                workspace_id="workspace",
                project_id="project",
                parent_id="folder",
                key_hash="1" * 64,
                request_hash="2" * 64,
                request_json={"_source_admission": asdict(admission)},
                total_bytes=7,
                expires_at=now + timedelta(days=1),
            )
        )
        await session.flush()
        session.add(
            SourceSyncObservation(
                id="initial-observation",
                tenant_id="retained",
                mapping_id="mapping",
                run_id="run",
                page_sequence=1,
                item_sequence=0,
                object_id="origin",
                generation=1,
                remote_version="v1",
                event_json={"name": "original.txt"},
                event_sha256="f" * 64,
                work_id="work",
            )
        )
        await session.flush()
        (await session.get(SourceSyncRun, "run")).page_sequence = 1
    lease = SimpleNamespace(
        tenant_id="retained",
        subject="issuer|alice",
        item_id="source-item",
        batch_id="source-batch",
        source_id="fresh-source",
        asset_id="fresh-asset",
        sha256="d" * 64,
        size_bytes=7,
    )
    return SimpleNamespace(sessions=sessions, uri=uri, admission=admission, lease=lease)


async def reserve_targets(session):
    for identifier, kind, parent in (
        ("fresh-source", "source", "folder"),
        ("fresh-asset", "document", "fresh-source"),
    ):
        session.add(
            CatalogEntry(
                id=identifier,
                tenant_id="retained",
                kind=kind,
                name="fresh",
                status="pending",
                workspace_id="workspace",
                project_id="project",
                parent_id=parent,
                created_by="issuer|alice",
            )
        )
        await session.flush()
    item = BulkItem(
        id="source-item",
        batch_id="source-batch",
        ordinal=0,
        client_item_id="remote-file",
        filename="report.docx",
        mode="document",
        size_bytes=7,
        sha256="d" * 64,
        source_id="fresh-source",
        asset_id="fresh-asset",
        status="awaiting_upload",
    )
    session.add(item)
    await session.flush()
    return item


async def bind(intake):
    async with intake.sessions.begin() as session:
        guard = SourceSyncIntake(session=session)
        await guard.admit(intake.admission)
        await guard.bind(intake.admission, 0, await reserve_targets(session))


async def test_binding_and_marker_are_atomic_and_reject_new_transaction_reuse(intake):
    async with intake.sessions.begin() as session:
        guard = SourceSyncIntake(session=session)
        await guard.admit(intake.admission)
        await guard.bind(intake.admission, 0, await reserve_targets(session))
        async with intake.sessions() as reader:
            assert await reader.get(SourceImportedAsset, "fresh-asset") is None
    async with intake.sessions() as reader:
        assert (await reader.get(SourceImportedAsset, "fresh-asset")).initial_attempt_id
    async with intake.sessions.begin() as other:
        with pytest.raises(ConflictException):
            await SourceSyncIntake(session=other).bind(
                intake.admission, 0, await other.get(BulkItem, "source-item")
            )


async def test_cancelled_receipt_preflight_reads_only_safe_identity_columns(intake):
    from sqlalchemy import Column, event

    await bind(intake)
    async with intake.sessions.begin() as session:
        await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            "mapping",
            "cancel",
            SourceControlInput(expected_revision=1, operation_id=str(uuid4())),
            target_run_id="run",
        )

    forbidden = {
        "secret_ciphertext",
        "policy_json",
        "event_json",
        "filename",
        "request_json",
        "payload",
        "descriptor_json",
        "receipt_json",
        "name",
        "description",
        "metadata_json",
    }
    selected = []

    def capture(_connection, _cursor, _statement, _parameters, context, _many):
        statement = context.compiled.statement if context.compiled is not None else None
        if statement is None or not statement.is_select:
            return
        selected.extend(
            column.name
            for column in statement.selected_columns
            if isinstance(column, Column) and column.name in forbidden
        )

    engine = intake.sessions.kw["bind"].sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        async with intake.sessions.begin() as session:
            await SourceSyncIntake(session=session).reconcile(intake.lease)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert selected == [], f"Receipt-only preflight hydrated protected columns: {selected}"
    async with intake.sessions() as session:
        assert (await session.get(SourceSyncRun, "run")).cancel_requested_at is not None
        assert (await session.get(SourceObject, "origin")).published_native_version_id is None


@pytest.mark.parametrize("change", [{"worker_id": "superseded"}, {"attempt": 2}])
async def test_receipt_recovery_rejects_a_superseded_bulk_execution(intake, change):
    from koinon.knowledge.bulk.dtos import BulkDestination
    from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
    from koinon.knowledge.bulk.repositories import BulkRepository
    from koinon.knowledge.bulk.settings import BulkSettings

    await bind(intake)
    async with intake.sessions.begin() as session:
        session.add(
            Job(
                id="intake-job",
                tenant_id="retained",
                resource_id="fresh-asset",
                kind="knowledge.bulk.intake",
                idempotency_key="intake-job",
                payload_hash="f" * 64,
                payload={},
                status="running",
                worker_id="original",
                attempts=1,
                lease_until=datetime.now(UTC) - timedelta(minutes=1),
            )
        )
        await session.flush()
        item = await session.get(BulkItem, "source-item")
        item.job_id, item.status, item.native_workspace_id = "intake-job", "running", "native-space"
    lease = BulkLease(
        job_id="intake-job",
        item_id="source-item",
        batch_id="source-batch",
        tenant_id="retained",
        subject="issuer|alice",
        token_id=None,
        worker_id="original",
        attempt=1,
        source_id="fresh-source",
        asset_id="fresh-asset",
        filename="report.docx",
        size_bytes=7,
        sha256="d" * 64,
        mode="document",
        destination=BulkDestination(workspace_id="workspace", project_id="project", parent_id="folder"),
    )
    async with intake.sessions.begin() as session:
        queue = BulkQueue(
            BulkRepository(session=session),
            None,
            BulkSettings(),
            None,
            source_fences=SimpleNamespace(get=lambda: SourceSyncIntake(session=session)),
        )
        # Expiry permits exact forensic correlation; it never authorizes another producer.
        await queue._reconcile_source(lease)
        with pytest.raises(ConflictException):
            await queue._reconcile_source(replace(lease, **change))


async def test_cancellation_blocks_old_run_publication_without_losing_reconciliation(intake):
    await bind(intake)
    async with intake.sessions.begin() as session:
        await SourceSyncIntake(session=session).check(intake.lease)
    async with intake.sessions.begin() as session:
        await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            "mapping",
            "cancel",
            SourceControlInput(expected_revision=1, operation_id=str(uuid4())),
            target_run_id="run",
        )
    async with intake.sessions.begin() as session:
        guard = SourceSyncIntake(session=session)
        with pytest.raises(ConflictException):
            await guard.check(intake.lease)
        await guard.reconcile(intake.lease)
        assert (await session.get(SourceObject, "origin")).generation == 1


@pytest.mark.parametrize(
    "action,expected", [("retire", ("excluded", 2, None)), ("cancel", ("pending", 1, None))]
)
async def test_cancelled_origin_receipt_is_retained_without_restoring_its_state(intake, action, expected):
    await bind(intake)
    async with intake.sessions.begin() as session:
        await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            "mapping",
            action,
            SourceControlInput(expected_revision=1, operation_id=str(uuid4())),
            target_run_id="run" if action == "cancel" else None,
        )
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
        guard = SourceSyncIntake(session=session)
        await guard.reconcile(intake.lease)
        await guard.committed(intake.lease, receipt)
    async with intake.sessions() as session:
        origin = await session.get(SourceObject, "origin")
        assert (origin.state, origin.generation, origin.published_native_version_id) == expected
        version = await session.scalar(select(SourceImportedVersion))
        assert version.native_version_id == "native-version"
        work = await session.get(SourceSyncWork, "work")
        assert work.status == "imported" and work.error_code is None


async def test_receipt_only_settlement_never_advances_an_otherwise_active_baseline(intake):
    await bind(intake)
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.publication_baselines import SourcePublicationBaselines

    async with intake.sessions.begin() as session:
        item = await session.get(BulkItem, "source-item")
        item.native_workspace_id = "native-space"
        attempt = await session.scalar(select(SourceImportAttempt))
        binding = await SourcePublicationBaselines(session).freeze(attempt, intake.admission, item)
    receipt = NativeCommit(
        "canon",
        "native-space",
        "native-source",
        "native-asset",
        "d" * 64,
        7,
        source_version_id="native-version",
        extraction_id="extraction",
        source_attempt_id=binding.attempt_id,
        source_publication_sha256=binding.descriptor_sha256,
    )
    for forged in (
        replace(receipt, source_attempt_id="other-attempt"),
        replace(receipt, source_publication_sha256="0" * 64),
        replace(receipt, sha256="0" * 64),
    ):
        async with intake.sessions.begin() as session:
            with pytest.raises(ConflictException):
                await SourceSyncIntake(session=session).settle(intake.lease, forged)
            assert (await session.get(SourceImportAttempt, binding.attempt_id)).receipt_json is None
    async with intake.sessions.begin() as session:
        guard = SourceSyncIntake(session=session)
        await guard.settle(intake.lease, receipt)
        await guard.settle(intake.lease, receipt)
    async with intake.sessions() as session:
        origin = await session.get(SourceObject, "origin")
        assert origin.state == "pending" and origin.published_native_version_id is None
        assert origin.published_local_revision is None and origin.published_sha256 is None
        assert (await session.get(SourceSyncWork, "work")).status == "conflict"
        assert await session.scalar(select(SourceImportedVersion)) is None


@pytest.mark.parametrize("commit_first", [True, False])
async def test_cancel_and_native_acknowledgement_serialize_without_reactivation(intake, commit_first):
    await bind(intake)
    locked, competing = asyncio.Event(), asyncio.Event()
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
    command = SourceControlInput(expected_revision=1, operation_id=str(uuid4()))

    async def cancel(session):
        return await SourceControlRepository(session=session).apply(
            "retained", "issuer|alice", "mapping", "cancel", command, target_run_id="run"
        )

    async def acknowledge(session):
        guard = SourceSyncIntake(session=session)
        await guard.reconcile(intake.lease)
        await guard.committed(intake.lease, receipt)

    async def first():
        async with intake.sessions.begin() as session:
            await (acknowledge(session) if commit_first else cancel(session))
            locked.set()
            await competing.wait()

    async def second():
        await locked.wait()
        async with intake.sessions.begin() as session:
            competing.set()
            await (cancel(session) if commit_first else acknowledge(session))

    await asyncio.wait_for(asyncio.gather(first(), second()), 10)
    async with intake.sessions.begin() as session:
        await acknowledge(session)
        await cancel(session)
        origin = await session.get(SourceObject, "origin")
        assert origin.generation == 1
        assert origin.published_native_version_id == ("native-version" if commit_first else None)
        assert (await session.get(SourceSyncWork, "work")).status == "imported"
        assert len(list((await session.scalars(select(SourceImportedVersion))).all())) == 1


async def test_retry_rejects_an_indeterminate_native_attempt(intake):
    await bind(intake)
    async with intake.sessions.begin() as session:
        run = await session.get(SourceSyncRun, "run")
        run.status = "partial"
        (await session.get(BulkItem, "source-item")).status = "reconciling"
    async with intake.sessions.begin() as session:
        policy = await session.get(SourceMappingPolicy, "accepted")
        capture = SyncAuthorityCapture(2, policy.authority_sha256, policy.id, policy.policy_sha256)
        with pytest.raises(JobConflict):
            await SourceControlRepository(session=session).apply(
                "retained",
                "issuer|alice",
                "mapping",
                "retry",
                SourceControlInput(expected_revision=1, operation_id=str(uuid4())),
                target_run_id="run",
                capture=capture,
            )


async def test_same_generation_metadata_aba_cannot_reuse_old_publication_admission(intake):
    await bind(intake)
    async with intake.sessions.begin() as session:
        run = await session.get(SourceSyncRun, "run", with_for_update=True)
        for position, name in enumerate(("renamed.txt", "original.txt")):
            session.add(
                SourceSyncObservation(
                    id="later-" + str(position),
                    tenant_id="retained",
                    mapping_id="mapping",
                    run_id="run",
                    page_sequence=run.page_sequence + 1,
                    item_sequence=position,
                    object_id="origin",
                    generation=1,
                    remote_version="v1",
                    event_json={"name": name},
                    event_sha256="a" * 64,
                    work_id="work",
                )
            )
        await session.flush()
        run.page_sequence += 1
    async with intake.sessions.begin() as session:
        with pytest.raises(ConflictException):
            await SourceSyncIntake(session=session).check(intake.lease)


async def test_new_run_advances_durable_scan_generation_with_control_receipt(intake):
    async with intake.sessions.begin() as session:
        (await session.get(SourceSyncRun, "run")).status = "succeeded"
    async with intake.sessions.begin() as session:
        policy = await session.get(SourceMappingPolicy, "accepted")
        result = await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            "mapping",
            "sync",
            SourceControlInput(expected_revision=1, operation_id=str(uuid4())),
            capture=SyncAuthorityCapture(2, policy.authority_sha256, policy.id, policy.policy_sha256),
        )
    async with intake.sessions() as session:
        state = await session.get(SourceSyncState, "mapping")
        run = await session.get(SourceSyncRun, result.run_id)
        assert state.scan_generation == run.scan_generation == 2


async def test_pause_stops_new_intake_but_allows_already_admitted_publication(intake):
    await bind(intake)
    async with intake.sessions.begin() as session:
        await SourceControlRepository(session=session).apply(
            "retained",
            "issuer|alice",
            "mapping",
            "pause",
            SourceControlInput(expected_revision=1, operation_id=str(uuid4())),
        )
    async with intake.sessions.begin() as session:
        guard = SourceSyncIntake(session=session)
        await guard.check(intake.lease)
        with pytest.raises(ConflictException):
            await guard.admit(intake.admission)


@pytest.mark.parametrize("publication_first", [False, True])
async def test_observation_and_publication_serialize_in_both_lock_orders(intake, publication_first):
    await bind(intake)
    locked, competing = asyncio.Event(), asyncio.Event()
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

    async def observe(session):
        run = await session.get(SourceSyncRun, "run")
        session.add(
            SourceSyncObservation(
                id="opposing-observation",
                tenant_id="retained",
                mapping_id="mapping",
                run_id="run",
                page_sequence=run.page_sequence + 1,
                item_sequence=0,
                object_id="origin",
                generation=1,
                remote_version="v1",
                event_json={"name": "changed"},
                event_sha256="a" * 64,
                work_id="work",
            )
        )
        await session.flush()
        run.page_sequence += 1

    async def first():
        async with intake.sessions.begin() as session:
            guard = SourceSyncIntake(session=session)
            await guard.check(intake.lease)
            if publication_first:
                await guard.committed(intake.lease, receipt)
            else:
                await observe(session)
            locked.set()
            await competing.wait()

    async def second():
        await locked.wait()
        async with intake.sessions.begin() as session:
            competing.set()
            guard = SourceSyncIntake(session=session)
            if publication_first:
                await guard.check(intake.lease)
                await observe(session)
            else:
                with pytest.raises(ConflictException):
                    await guard.check(intake.lease)

    await asyncio.wait_for(asyncio.gather(first(), second()), timeout=10)
    async with intake.sessions() as session:
        versions = list((await session.scalars(select(SourceImportedVersion))).all())
        assert len(versions) == (1 if publication_first else 0)
        if publication_first:
            assert versions[0].native_version_id == "native-version"


async def test_new_generation_cannot_restart_an_indeterminate_prior_native_attempt(intake):
    await bind(intake)
    async with intake.sessions.begin() as session:
        (await session.get(BulkItem, "source-item")).status = "reconciling"
        origin = await session.get(SourceObject, "origin")
        origin.generation, origin.remote_version = 2, "v2"
        session.add(
            SourceSyncWork(
                id="next-work",
                tenant_id="retained",
                mapping_id="mapping",
                object_id="origin",
                generation=2,
                remote_version="v2",
                event_sha256="a" * 64,
                status="admitted",
                error_code=None,
                attempt_id=None,
                expected_local_revision=None,
                expected_sha256=None,
            )
        )
        await session.flush()
        session.add(
            SourceSyncObservation(
                id="next-observation",
                tenant_id="retained",
                mapping_id="mapping",
                run_id="run",
                page_sequence=2,
                item_sequence=0,
                object_id="origin",
                generation=2,
                remote_version="v2",
                event_json={},
                event_sha256="a" * 64,
                work_id="next-work",
            )
        )
        await session.flush()
        (await session.get(SourceSyncRun, "run")).page_sequence = 2
    candidate = replace(
        intake.admission,
        items=(SourceIntakeItem("origin", 2, "v2", "next-observation", "next-work", 2, 0, "a" * 64),),
    )
    async with intake.sessions.begin() as session:
        with pytest.raises(ConflictException):
            await SourceSyncIntake(session=session).admit(candidate)
