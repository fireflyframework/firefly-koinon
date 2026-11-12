# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private publication grants cannot become reusable or transferable reader authority."""

import asyncio
from copy import copy
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import source_database as source_database
from test_sync_intake_postgres import bind
from test_sync_intake_postgres import intake as intake

from koinon.integrations.content_sources.sync_entities import SourceSyncRun
from koinon.integrations.content_sources.sync_intake import SourceSyncIntake
from koinon.integrations.content_sources.sync_runs import SourceRunLease
from koinon.jobs.entities import Job

pytestmark = pytest.mark.integration


@pytest.fixture
async def execution(intake):
    async with intake.sessions.begin() as session:
        run = await session.get(SourceSyncRun, "run")
        job = await session.get(Job, run.job_id)
        job.attempts = 1
        return SourceRunLease(
            "retained",
            "issuer|alice",
            "mapping",
            run.id,
            job.id,
            job.worker_id,
            job.attempts,
            run.mapping_revision,
            run.connection_revision,
            run.policy_id,
            job.lease_until,
            False,
        )


async def test_publication_without_an_execution_lease_is_denied(intake):
    from koinon.integrations.content_sources.source_publication import SourcePublicationWriter

    async with intake.sessions.begin() as session:
        writer = SourcePublicationWriter(
            SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
        )
        writer._fresh = AsyncMock()
        with pytest.raises(ConflictException):
            async with writer.prepare(intake.admission), writer.fence(intake.admission):
                pass


@pytest.mark.parametrize("change", [None, "remove_omitted", "snapshot", "locator"])
async def test_replacement_freeze_requires_the_complete_original_member_plan(change):
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from koinon.integrations.content_sources.source_publication import SourcePublicationWriter
    from koinon.integrations.content_sources.sync_runs import SourceReplacementExecution
    from koinon.knowledge.bulk.structured_dtos import ReplacementMemberPlan

    live = ReplacementMemberPlan(
        member_key="root",
        action="retain",
        table_id=uuid4(),
        catalog_table_id="table",
        snapshot_id=uuid4(),
        ordinal=0,
        name="Facts",
    )
    removed = ReplacementMemberPlan(
        member_key='worksheet:["old"]',
        action="remove",
        table_id=uuid4(),
        catalog_table_id="removed-table",
        snapshot_id=uuid4(),
        ordinal=None,
        name=None,
    )
    members = (live, removed)
    header = SimpleNamespace(
        descriptor_json={"members": [member.model_dump(mode="json", by_alias=True) for member in members]},
        descriptor_sha256="a" * 64,
    )
    lease = SourceRunLease(
        "tenant",
        "owner",
        "mapping",
        "run",
        "job",
        "worker",
        1,
        1,
        1,
        "policy",
        datetime.now(UTC) + timedelta(minutes=1),
        False,
    )
    execution = SourceReplacementExecution(lease, "attempt", "operation")
    admission = object()
    writer = SimpleNamespace(
        require_fence=lambda value: None,
        replacement_attempt=AsyncMock(return_value=(SimpleNamespace(id="attempt"), header)),
        intake=SimpleNamespace(_require_session=lambda: None),
    )
    if change == "remove_omitted":
        members = (live,)
    elif change == "snapshot":
        members = (live.model_copy(update={"snapshot_id": uuid4()}), removed)
    elif change == "locator":
        members = (live.model_copy(update={"member_key": "different"}), removed)
    if change is None:
        binding = await SourcePublicationWriter.freeze_publication(
            writer, admission, execution=execution, members=members
        )
        assert (binding.attempt_id, binding.descriptor_sha256) == ("attempt", "a" * 64)
    else:
        with pytest.raises(ConflictException):
            await SourcePublicationWriter.freeze_publication(
                writer, admission, execution=execution, members=members
            )


@pytest.mark.parametrize("change", [None, "file_id", "catalog_source_id", "filename", "sha256"])
async def test_structured_replacement_producer_binds_the_retained_private_operation(change):
    from contextlib import asynccontextmanager
    from datetime import UTC, datetime, timedelta
    from uuid import uuid4

    from koinon.integrations.content_sources.source_publication import SourcePublicationWriter
    from koinon.integrations.content_sources.sync_runs import SourceReplacementExecution
    from koinon.knowledge.bulk.structured_dtos import StructuredOperationIdentity

    identity = StructuredOperationIdentity(
        operation_id=uuid4(), tenant_id="tenant", workspace_id=uuid4(), dataset_id=uuid4(),
        file_id=uuid4(), actor="owner", catalog_source_id="source", catalog_dataset_id="dataset",
        catalog_file_version_id="version", filename="facts.csv", sha256="a" * 64, size_bytes=7,
    )
    lease = SourceRunLease(
        "tenant", "owner", "mapping", "run", "job", "worker", 1, 1, 1, "policy",
        datetime.now(UTC) + timedelta(minutes=1), False,
    )
    execution = SourceReplacementExecution(lease, "attempt", str(identity.operation_id))
    admission = SimpleNamespace(tenant_id="tenant", owner="owner")
    attempt = SimpleNamespace(
        id="attempt", content_operation_id=str(identity.operation_id), source_id="source", asset_id="dataset",
        sha256="a" * 64, size_bytes=7,
    )
    marker = {
        "attempt_id": "attempt", "previous_attempt_id": "previous",
        "native_workspace_id": str(identity.workspace_id), "native_dataset_id": str(identity.dataset_id),
        "native_file_id": str(identity.file_id),
    }
    stored = SimpleNamespace(
        name="facts.csv", metadata_json={"_koinon_source_replacement": marker}
    )
    header = SimpleNamespace(
        producer_kind="replace_dataset", previous_attempt_id="previous",
        descriptor_json={"native": {"domain": "structured", "workspace_id": str(identity.workspace_id)},
                         "targets": [{"pin": {"role": "new_index", "catalog_id": "version"}}]},
    )
    lineage = SimpleNamespace(sink=lambda **kwargs: object())
    writer = SourcePublicationWriter(
        SimpleNamespace(_require_session=lambda: SimpleNamespace(get=AsyncMock(return_value=stored))),
        object(), lineage=SimpleNamespace(get=lambda: lineage),
    )
    writer.require_fence = lambda value: None
    writer.replacement_attempt = AsyncMock(return_value=(attempt, header))

    @asynccontextmanager
    async def publication():
        yield admission

    if change:
        value = uuid4() if change == "file_id" else "b" * 64 if change == "sha256" else "changed"
        identity = identity.model_copy(update={change: value})
        with pytest.raises(ConflictException):
            async with writer.structured_producer(
                admission, execution=execution, operation=identity, publication=publication
            ):
                pytest.fail("A substituted operation acquired the native producer")
    else:
        async with writer.structured_producer(
            admission, execution=execution, operation=identity, publication=publication
        ) as producer:
            assert producer.operation == identity and producer.attempt_id == "attempt"
            producer.check()
        with pytest.raises(ConflictException):
            producer.check()


@pytest.mark.parametrize("relative_path", [(), ("file",), ("parent",)])
async def test_single_file_publication_keeps_actual_parent_separate_from_relative_path(
    monkeypatch, relative_path
):
    from contextlib import asynccontextmanager
    from dataclasses import asdict

    from koinon.integrations.content_sources import source_publication
    from koinon.integrations.content_sources.dtos import Account, RemoteItem, SourceScope
    from koinon.integrations.content_sources.sync_entities import SourceMappingPolicy

    scope = SourceScope(Account("google_drive", "external"), "drive")
    selected = RemoteItem(scope, "file", "facts.txt", "file", "v1", 7, "text/plain", ("parent",), True)
    rows = {
        "file": selected,
        "parent": RemoteItem(scope, "parent", "Private", "folder", "v1", None, "", ("root",)),
        "root": RemoteItem(scope, "root", "Drive", "folder", "v1", None, "", ()),
    }

    class Source:
        async def root(self):
            return rows["root"]

        async def get_item(self, identifier):
            return rows[identifier]

        async def check_access(self, identifier):
            assert identifier == "file"
            return selected

    @asynccontextmanager
    async def remote(*args, **kwargs):
        yield Source()

    @asynccontextmanager
    async def local(**kwargs):
        yield

    policy = SimpleNamespace(
        id="policy", policy_sha256="a" * 64, authority_sha256="b" * 64,
        root_ancestry_json=["file", "parent", "root"], policy_json={"root_kind": "file"},
    )

    async def get(kind, identifier):
        return policy if kind is SourceMappingPolicy else SimpleNamespace(
            event_json={"item": asdict(selected), "ancestry": list(relative_path)}
        )

    mapping = SimpleNamespace(provider="google_drive", external_subject="external", external_tenant=None,
                              connection_id="connection", drive_id="drive", root_id="file")
    grant = SimpleNamespace(revision=1, token="local-test-token")
    mappings = SimpleNamespace(
        remote_capture=AsyncMock(), browser=SimpleNamespace(_source=remote),
        connections=SimpleNamespace(read_grant=AsyncMock(return_value=grant), confirm_read_grant=AsyncMock()),
    )
    writer = source_publication.SourcePublicationWriter(
        SimpleNamespace(
            _require_session=lambda: SimpleNamespace(get=get),
            _fence=AsyncMock(return_value=(mapping, {"object": SimpleNamespace(item_id="file")},
                                          SimpleNamespace(policy_id="policy"))),
        ),
        SimpleNamespace(source_destination=AsyncMock(),
                        catalog=SimpleNamespace(_refresh_managed_memberships=AsyncMock())),
        SimpleNamespace(get=lambda: mappings),
    )
    writer._execution = AsyncMock()
    monkeypatch.setattr(source_publication, "primary_authority", local)
    admission = SimpleNamespace(
        owner="owner", tenant_id="tenant", connection_revision=1,
        items=(SimpleNamespace(object_id="object", observation_id="observation", remote_version="v1"),),
    )
    if relative_path:
        with pytest.raises(ConflictException):
            await writer._fresh(admission, object())
    else:
        await writer._fresh(admission, object())
        mappings.connections.confirm_read_grant.assert_awaited_once()


async def test_replacement_fence_binds_exact_command_and_current_run_lease(
    source_sessions, source_database, monkeypatch
):
    from dataclasses import replace
    from datetime import UTC, datetime, timedelta
    from functools import partial

    import psycopg
    import test_source_publication_baselines_postgres as publication_fixture
    from sqlalchemy import select
    from test_source_migration_postgres import load
    from test_source_publication_baselines_postgres import (
        freeze,
        pin,
        publish_document,
        reserve_document,
        reserve_document_replacement,
    )

    from koinon.integrations.content_sources.entities import PersonalSourceConnection
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.publication_baselines import SourcePublicationBaselines
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
    from koinon.integrations.content_sources.read_authority import source_authority
    from koinon.integrations.content_sources.source_publication import (
        SourcePublicationWriter,
        SourceWriteOperation,
        consume_write,
    )
    from koinon.integrations.content_sources.sync_checkpoints import SourceCheckpoints
    from koinon.integrations.content_sources.sync_entities import SourceSyncObservation
    from koinon.integrations.content_sources.sync_runs import SourceReplacementExecution
    from koinon.knowledge.bulk.ports import SourceIntakeAdmission

    sessions, uri = source_sessions
    async with sessions.begin() as session:
        account = await session.get(PersonalSourceConnection, "connection")
        account.config_fingerprint = "a" * 64
        authority_digest = source_authority(account)[1]
    monkeypatch.setattr(
        publication_fixture, "policy", partial(publication_fixture.policy, authority_sha256=authority_digest)
    )
    with psycopg.connect(uri) as connection:
        for table in (
            "lattice_jobs",
            "lattice_domain_bindings",
            "koinon_content_policies",
            "koinon_content_sync_states",
            "koinon_content_sync_runs",
            "koinon_content_sync_work",
            "koinon_content_sync_observations",
            "koinon_content_folder_bindings",
            "koinon_content_folder_publications",
            "koinon_content_imported_assets",
            "koinon_content_imported_versions",
            "koinon_content_publication_baselines",
            "koinon_content_publication_targets",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, source_database[1])
        source, asset, _ = reserve_document(connection)
        connection.execute("UPDATE lattice_catalog SET name='Other retained source' WHERE id='source'")
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        _, digest = freeze(connection)
        connection.commit()
        publish_document(connection, digest)
        connection.commit()
        reserve_document_replacement(connection)
        connection.execute(
            "INSERT INTO koinon_content_sync_states(mapping_id,tenant_id,accepted_policy_id,enabled,"
            "revision,scan_generation,last_complete_scan_generation,updated_at) "
            "VALUES('mapping','retained','policy-mapping',true,1,1,0,now())"
        )
        connection.execute("UPDATE koinon_content_sync_work SET status='processing' WHERE id='work2'")
        connection.execute("UPDATE koinon_content_sync_runs SET status='running' WHERE id='first'")
        connection.execute(
            "UPDATE lattice_jobs SET status='running',worker_id='worker',attempts=1,"
            "lease_until=now()+interval '5 minutes' WHERE id='job-first'"
        )
    async with sessions.begin() as session:
        run = await session.get(SourceSyncRun, "first")
        from koinon.integrations.content_sources.mapping_entities import SourceMapping
        from koinon.integrations.content_sources.sync_entities import SourceMappingPolicy, SourceSyncState

        account = await session.get(PersonalSourceConnection, "connection")
        mapping = await session.get(SourceMapping, "mapping")
        control = await session.get(SourceSyncState, "mapping")
        policy = await session.get(SourceMappingPolicy, run.policy_id)
        assert mapping.status == "active" and mapping.revision == run.mapping_revision
        assert account.status == "connected" and account.revision == run.connection_revision
        assert account.secret_ciphertext and account.refresh_operation is None
        assert control.accepted_policy_id == run.policy_id and policy.accepted_at is not None
        assert policy.authority_sha256 == source_authority(account)[1]
        assert run.status == "running" and run.cancel_requested_at is None
        job = await session.get(Job, run.job_id)
        observation = await session.get(SourceSyncObservation, "observation2")
        admission = SourceIntakeAdmission(
            "retained",
            "issuer|alice",
            "mapping",
            run.mapping_revision,
            run.connection_revision,
            run.id,
            ("workspace", "project", "folder"),
            (SourceCheckpoints.pin(observation),),
        )
        execution = SourceReplacementExecution(
            SourceRunLease(
                admission.tenant_id,
                admission.owner,
                admission.mapping_id,
                run.id,
                job.id,
                job.worker_id,
                job.attempts,
                run.mapping_revision,
                run.connection_revision,
                run.policy_id,
                job.lease_until,
                False,
            ),
            "attempt2",
            "replacement",
        )
        attempt = await session.get(SourceImportAttempt, execution.attempt_id)
        retained = await SourcePublicationBaselines(session).freeze_replacement(attempt, admission)
        assert retained.attempt_id == execution.attempt_id and retained.descriptor_sha256
        baseline = await session.get(SourcePublicationBaseline, attempt.id)
        planned = tuple(
            SourceWriteOperation(
                write["action"],
                target["pin"]["catalog_id"],
                target["pin"]["parent_id"],
                write["fields"],
                target["pin"]["mutation_revision"] + offset,
            )
            for target in baseline.descriptor_json["targets"]
            for offset, write in enumerate(target["writes"])
        )
    for operations in (
        planned,
        (replace(planned[0], changes={"name": "Unreviewed rename"}), *planned[1:]),
        (replace(planned[0], changes={"status": "ready"}), *planned[1:]),
        planned[:1],
    ):
        entered = False
        async with sessions.begin() as session:
            writer = SourcePublicationWriter(
                SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
            )
            writer._fresh = AsyncMock()
            try:
                async with (
                    writer.prepare(admission, execution=execution),
                    writer.fence(admission),
                    writer.open(admission, operations) as permit,
                ):
                    entered = True
                    for operation in operations:
                        consume_write(
                            permit,
                            session,
                            actor=admission.owner,
                            tenant=admission.tenant_id,
                            action=operation.action,
                            target=operation.target,
                            parent=operation.parent,
                            changes=operation.changes,
                        )
            except ConflictException:
                assert operations != planned
            assert entered is (operations == planned)
    for changed in (
        None,
        replace(execution, attempt_id="attempt"),
        replace(execution, content_operation_id="foreign"),
        replace(execution, run_lease=replace(execution.run_lease, worker_id="foreign")),
    ):
        async with sessions.begin() as session:
            writer = SourcePublicationWriter(
                SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
            )
            writer._fresh = AsyncMock()
            if changed is None:
                async with writer.prepare(admission, execution=execution), writer.fence(admission):
                    assert (await writer.replacement_attempt(admission, execution))[0].id == "attempt2"
            else:
                with pytest.raises(ConflictException):
                    async with writer.prepare(admission, execution=changed), writer.fence(admission):
                        pytest.fail("A different replacement producer cannot enter publication")
    async with sessions.begin() as session:
        job = await session.get(Job, execution.run_lease.job_id)
        job.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    async with sessions.begin() as session:
        writer = SourcePublicationWriter(
            SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
        )
        writer._fresh = AsyncMock()
        with pytest.raises(ConflictException):
            async with writer.prepare(admission, execution=execution), writer.fence(admission):
                pytest.fail("An expired replacement worker cannot publish")
        assert (
            await session.scalar(select(SourceImportAttempt).where(SourceImportAttempt.id == "attempt2"))
        ).receipt_json is None


@pytest.mark.parametrize(
    "change", [None, "job", "worker", "attempt", "expired", "source", "batch", "resource", "payload"]
)
async def test_bulk_publication_requires_the_exact_live_bound_attempt(intake, change):
    from dataclasses import replace
    from datetime import UTC, datetime, timedelta

    from koinon.integrations.content_sources.source_publication import (
        SourcePublicationWriter,
        SourceWriteOperation,
        consume_write,
    )
    from koinon.knowledge.bulk.dtos import BulkDestination
    from koinon.knowledge.bulk.entities import BulkItem
    from koinon.knowledge.bulk.queue import BulkLease

    await bind(intake)
    expires = datetime.now(UTC) + timedelta(minutes=2)
    async with intake.sessions.begin() as session:
        session.add(
            Job(
                id="bulk-job",
                tenant_id="retained",
                resource_id="wrong" if change == "resource" else "fresh-asset",
                kind="knowledge.bulk.intake",
                idempotency_key="bulk-job",
                payload_hash="e" * 64,
                payload={
                    "batch_id": "source-batch",
                    "item_id": "wrong" if change == "payload" else "source-item",
                },
                status="running",
                worker_id="bulk-worker",
                attempts=1,
                lease_until=expires if change != "expired" else datetime.now(UTC) - timedelta(seconds=1),
            )
        )
        await session.flush()
        item = await session.get(BulkItem, "source-item")
        item.job_id, item.status = "bulk-job", "running"
    proof = BulkLease(
        "bulk-job",
        "source-item",
        "source-batch",
        "retained",
        "issuer|alice",
        None,
        "bulk-worker",
        1,
        "fresh-source",
        "fresh-asset",
        "report.docx",
        7,
        "d" * 64,
        "document",
        BulkDestination(workspace_id="workspace", project_id="project", parent_id="folder"),
        expires_at=expires,
    )
    changes = {
        "job": {"job_id": "source-run"},
        "worker": {"worker_id": "different"},
        "attempt": {"attempt": 2},
        "source": {"source_id": "other"},
        "batch": {"batch_id": "batch"},
    }
    proof = replace(proof, **changes.get(change, {}))

    async def publish():
        async with intake.sessions.begin() as session:
            writer = SourcePublicationWriter(
                SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
            )
            writer._fresh = AsyncMock()
            async with (
                writer.prepare(intake.admission, execution=proof),
                writer.fence(intake.admission),
                writer.open(
                    intake.admission,
                    (SourceWriteOperation("update", "fresh-source", "folder", {"status": "ready"}, 1),),
                ) as permit,
            ):
                descriptor = consume_write(
                    permit,
                    session,
                    actor="issuer|alice",
                    tenant="retained",
                    action="update",
                    target="fresh-source",
                    parent="folder",
                    changes={"status": "ready"},
                )
                assert descriptor.expected_revision == 1 and permit.operations == {}

    if change is None:
        await publish()
    else:
        with pytest.raises(ConflictException):
            await publish()


async def test_publication_fence_requires_one_fresh_remote_preparation(intake):
    from koinon.integrations.content_sources.source_publication import SourcePublicationWriter

    async with intake.sessions.begin() as session:
        writer = SourcePublicationWriter(
            SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
        )
        with pytest.raises(ConflictException):
            async with writer.fence(intake.admission):
                pytest.fail("Local source identity is not fresh provider permission")


async def test_private_destination_uses_only_identity_projection_and_same_ancestry_rules(
    intake, source_database
):
    from dataclasses import replace

    import psycopg
    from test_source_migration_postgres import load

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.bulk.authority import BulkAuthority
    from koinon.knowledge.bulk.repositories import BulkRepository

    _, role, _ = source_database
    with psycopg.connect(intake.uri) as connection:
        for table in ("lattice_tenants", "lattice_memberships"):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
        connection.execute("UPDATE lattice_catalog SET project_id=NULL WHERE id='workspace'")
        connection.execute("UPDATE lattice_catalog SET kind='collection' WHERE id='folder'")
    catalog = SimpleNamespace(
        authorize=AsyncMock(),
        restriction=None,
        get=AsyncMock(side_effect=AssertionError("Reader hydration is forbidden")),
    )
    async with intake.sessions.begin() as session:
        authority = BulkAuthority(catalog, BulkRepository(session=session))
        await authority.source_destination(intake.admission)
        with pytest.raises(AccessDenied):
            await authority.source_destination(
                replace(intake.admission, destination=("other", "project", "folder"))
            )
        catalog.get.assert_not_awaited()


async def test_source_write_permit_is_exact_one_use_task_and_transaction_bound(intake, execution):
    from koinon.integrations.content_sources.source_publication import (
        SourcePublicationWriter,
        SourceWriteOperation,
        consume_write,
    )

    async with intake.sessions.begin() as session:
        guard = SourceSyncIntake(session=session)
        writer = SourcePublicationWriter(guard, SimpleNamespace(source_destination=AsyncMock()))
        writer._fresh = AsyncMock()  # Remote preparation is separate from these capability boundary checks.
        operation = SourceWriteOperation("create", "new-source", "folder", {"kind": "source", "name": "new"})
        with pytest.raises(ConflictException):
            async with writer.prepare(intake.admission, execution=execution), writer.fence(intake.admission):
                with pytest.raises(ConflictException):
                    async with writer.open(intake.admission, (operation,)) as permit:

                        def consume(candidate=permit, **overrides):
                            return consume_write(
                                candidate,
                                session,
                                **{
                                    "actor": "issuer|alice",
                                    "tenant": "retained",
                                    "action": "create",
                                    "target": "new-source",
                                    "parent": "folder",
                                    "changes": {"kind": "source", "name": "new"},
                                    **overrides,
                                },
                            )

                        with pytest.raises(ConflictException):
                            consume(copy(permit))

                        async def child():
                            with pytest.raises(ConflictException):
                                consume()

                        await asyncio.create_task(child())
                        consume()
                        with pytest.raises(ConflictException):
                            consume()
                with pytest.raises(ConflictException):
                    consume()
        with pytest.raises(ConflictException):
            async with writer.open(intake.admission, (operation,)):
                pass


@pytest.mark.parametrize(
    "change",
    [
        {"actor": "issuer|other"},
        {"tenant": "other"},
        {"action": "update"},
        {"target": "another"},
        {"parent": "another"},
        {"changes": {"name": "forged"}},
    ],
)
async def test_wrong_write_descriptor_invalidates_grant_without_fallback(intake, execution, change):
    from koinon.integrations.content_sources.source_publication import (
        SourcePublicationWriter,
        SourceWriteOperation,
        consume_write,
    )

    async with intake.sessions.begin() as session:
        writer = SourcePublicationWriter(
            SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
        )
        operation = SourceWriteOperation("create", "new-source", "folder", {"name": "new"})
        writer._fresh = AsyncMock()
        with pytest.raises(ConflictException):
            async with (
                writer.prepare(intake.admission, execution=execution),
                writer.fence(intake.admission),
                writer.open(intake.admission, (operation,)) as permit,
            ):
                expected = dict(
                    actor="issuer|alice",
                    tenant="retained",
                    action="create",
                    target="new-source",
                    parent="folder",
                    changes={"name": "new"},
                )
                with pytest.raises(ConflictException):
                    consume_write(permit, session, **{**expected, **change})
                with pytest.raises(ConflictException):
                    consume_write(permit, session, **expected)


async def test_catalog_decorator_consumes_private_permit_before_any_reader_check(intake, execution):
    from koinon.catalog.source_mutations import source_mutation
    from koinon.integrations.content_sources.source_publication import (
        SourcePublicationWriter,
        SourceWriteOperation,
    )

    async with intake.sessions.begin() as session:
        called = []

        class Catalog:
            catalog_repository = SimpleNamespace(_require_session=lambda: session)
            source_policy = SimpleNamespace(
                get=lambda: SimpleNamespace(
                    mutation=lambda *args, **kwargs: (_ for _ in ()).throw(
                        AssertionError("provider inside unit")
                    )
                )
            )

            @source_mutation
            async def create(
                self,
                subject,
                tenant_id,
                *,
                kind,
                name,
                parent_id=None,
                metadata=None,
                description="",
                _source_create_id=None,
            ):
                called.append(_source_create_id)

        writer = SourcePublicationWriter(
            SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
        )
        changes = dict(kind="source", name="new", metadata={}, description="")
        operation = SourceWriteOperation("create", "new-source", "folder", changes)
        writer._fresh = AsyncMock()
        async with (
            writer.prepare(intake.admission, execution=execution),
            writer.fence(intake.admission),
            writer.open(intake.admission, (operation,)) as permit,
        ):
            await Catalog().create(
                "issuer|alice",
                "retained",
                kind="source",
                name="new",
                parent_id="folder",
                _source_create_id="new-source",
                _source_write=permit,
            )
        assert called == ["new-source"]
        with pytest.raises(ConflictException):
            await Catalog().create(
                "issuer|alice",
                "retained",
                kind="source",
                name="new",
                parent_id="folder",
                _source_create_id="new-source",
                _source_write=permit,
            )
        assert called == ["new-source"]


async def test_publication_state_projects_only_exact_admitted_target(intake, execution):
    from dataclasses import asdict

    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.source_publication import (
        SourcePublicationWriter,
        SourceWriteOperation,
    )

    await bind(intake)
    async with intake.sessions.begin() as session:
        writer = SourcePublicationWriter(
            SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
        )
        operation = SourceWriteOperation(
            "update", "fresh-source", "folder", {"status": "ready"}, expected_revision=1
        )
        catalog = SimpleNamespace(catalog_repository=SimpleNamespace(_require_session=lambda: session))
        writer._fresh = AsyncMock()
        with pytest.raises(ConflictException):  # An unused write descriptor cannot commit.
            async with (
                writer.prepare(intake.admission, execution=execution),
                writer.fence(intake.admission),
                writer.open(intake.admission, (operation,)) as permit,
            ):
                state = await CatalogService._publication_state(catalog, permit, "fresh-source")
                assert asdict(state) == dict(
                    id="fresh-source", mutation_revision=1, status="ready", latest_content_version_id=None
                )
                with pytest.raises(ConflictException):
                    await CatalogService._publication_state(catalog, permit, "fresh-asset")
        with pytest.raises(ConflictException):
            await CatalogService._publication_state(catalog, permit, "fresh-source")


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_failed_domain_write_invalidates_all_remaining_descriptors(intake, execution, failure):
    from koinon.catalog.source_mutations import source_mutation
    from koinon.integrations.content_sources.source_publication import (
        SourcePublicationWriter,
        SourceWriteOperation,
        consume_write,
    )

    async with intake.sessions.begin() as session:

        class Catalog:
            catalog_repository = SimpleNamespace(_require_session=lambda: session)

            @source_mutation
            async def create(
                self,
                subject,
                tenant_id,
                *,
                kind,
                name,
                parent_id=None,
                metadata=None,
                description="",
                _source_create_id=None,
            ):
                raise failure()

        writer = SourcePublicationWriter(
            SourceSyncIntake(session=session), SimpleNamespace(source_destination=AsyncMock())
        )
        writer._fresh = AsyncMock()
        changes = dict(kind="source", name="new", description="", metadata={})
        operations = tuple(
            SourceWriteOperation("create", identifier, "folder", changes) for identifier in ("one", "two")
        )
        with pytest.raises(ConflictException):
            async with (
                writer.prepare(intake.admission, execution=execution),
                writer.fence(intake.admission),
                writer.open(intake.admission, operations) as permit,
            ):
                with pytest.raises(failure):
                    await Catalog().create(
                        "issuer|alice",
                        "retained",
                        kind="source",
                        name="new",
                        parent_id="folder",
                        _source_create_id="one",
                        _source_write=permit,
                    )
                with pytest.raises(ConflictException):
                    consume_write(
                        permit,
                        session,
                        actor="issuer|alice",
                        tenant="retained",
                        action="create",
                        target="two",
                        parent="folder",
                        changes=changes,
                    )
