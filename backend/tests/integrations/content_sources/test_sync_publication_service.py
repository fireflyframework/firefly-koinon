# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Provider permission and canonical ACLs are both required before private writes."""

from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.kernel import ConflictException
from sqlalchemy import update
from test_connection_lifecycle import lifecycle as lifecycle
from test_mapping_policy_service import empty_listing as empty_listing
from test_mapping_review import review as review
from test_source_migration_postgres import source_database as source_database

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.dtos import RemoteItem, SourceScope
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.lifecycle import _no_remote_unit
from koinon.integrations.content_sources.mapping_policies import SourcePolicies
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.source_publication import (
    SourcePublicationWriter,
    SourceWriteOperation,
)
from koinon.integrations.content_sources.sync_checkpoints import SourceCheckpoints
from koinon.integrations.content_sources.sync_dtos import (
    SourceControlInput,
    SourcePolicyApplyInput,
    SourcePolicyReviewInput,
)
from koinon.integrations.content_sources.sync_intake import SourceSyncIntake
from koinon.integrations.content_sources.sync_runs import SourceRunRepository
from koinon.integrations.content_sources.sync_walk import WalkItem, WalkPage
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.authority import BulkAuthority
from koinon.knowledge.bulk.ports import SourceIntakeAdmission
from koinon.security.authority import primary_authority


async def assert_revoked_native_receipt_is_private(current, restarted, receipt):
    from sqlalchemy import event, func, select

    from koinon.catalog.entities import AuditEvent, CatalogEntry
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline

    value, lease = current.producer, current.lease
    async with primary_authority(read_only=False):
        session = value.guard._require_session()
        revisions = dict((await session.execute(select(CatalogEntry.id, CatalogEntry.mutation_revision).where(
            CatalogEntry.id.in_((lease.source_id, lease.asset_id))
        ))).all())
        engine = session.get_bind()
        await session.execute(update(Membership).where(Membership.id == lease.subject).values(role="viewer"))
    with pytest.raises(AccessDenied):
        await restarted.acknowledge(lease, receipt)
    calls = len(value.review.state.calls)
    statements = []

    def capture_statement(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture_statement)
    try:
        observed = await restarted.inspect_committed(lease)
        assert observed.status == "committed" and observed.receipt == receipt
        await restarted.settle_source_receipt(lease, receipt)
        await restarted.settle_source_receipt(lease, receipt)
    finally:
        event.remove(engine, "before_cursor_execute", capture_statement)
    assert len(value.review.state.calls) == calls
    assert statements and all(
        field not in statement for statement in statements for field in (
            "lattice_catalog.name", "lattice_catalog.metadata_json",
            "koinon_content_connections.secret_ciphertext", "koinon_content_sync_observations.event_json",
            "koinon_content_policies.policy_json",
        )
    )
    async with primary_authority():
        session = value.guard._require_session()
        baseline = await session.get(SourcePublicationBaseline, receipt.source_attempt_id)
        attempt = await session.get(SourceImportAttempt, receipt.source_attempt_id)
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        assert baseline.acknowledgement_json is None
        assert attempt.receipt_json["source_attempt_id"] == receipt.source_attempt_id
        assert origin.published_native_version_id is None and origin.published_local_revision is None
        assert dict((await session.execute(select(CatalogEntry.id, CatalogEntry.mutation_revision).where(
            CatalogEntry.id.in_(revisions)
        ))).all()) == revisions
        assert await session.scalar(select(func.count()).select_from(AuditEvent).where(
            AuditEvent.action == "knowledge.source.receipt_recorded", AuditEvent.resource_id == lease.item_id
        )) == 1


@pytest.mark.parametrize("change", ["order", "missing", "extra", "table", "snapshot", "file", "operation"])
def test_replacement_receipt_rejects_an_altered_complete_member_set(change):
    from koinon.integrations.content_sources.replacement_receipts import ReplacementReceiptIdentity
    from koinon.knowledge.bulk.ports import NativeCommit, NativeTableCommit

    identity = ReplacementReceiptIdentity(
        "attempt", "operation", "source", "asset", "a" * 64, 17, "structured", "b" * 64,
        "workspace", "native-source", "dataset", "native-file",
        (("catalog-a", "table-a", "snapshot-a"), ("catalog-b", "table-b", "snapshot-b")), False,
    )
    receipt = NativeCommit(
        "structured", "workspace", "native-source", "dataset", "a" * 64, 17,
        file_version_id="operation", native_file_id="native-file",
        tables=(NativeTableCommit("catalog-a", "table-a", "snapshot-a", 1, 2),
                NativeTableCommit("catalog-b", "table-b", "snapshot-b", 1, 3)),
        source_attempt_id="attempt", source_publication_sha256="b" * 64,
    )
    assert identity.matches(receipt)
    if change == "order":
        altered = replace(receipt, tables=receipt.tables[::-1])
    elif change == "missing":
        altered = replace(receipt, tables=receipt.tables[:1])
    elif change == "extra":
        altered = replace(receipt, tables=(*receipt.tables, NativeTableCommit("catalog-c", "c", "c", 1, 2)))
    elif change == "table":
        altered = replace(receipt, tables=(replace(receipt.tables[0], table_id="table-c"), receipt.tables[1]))
    elif change == "snapshot":
        altered = replace(
            receipt, tables=(receipt.tables[0], replace(receipt.tables[1], snapshot_id="previous"))
        )
    elif change == "file":
        altered = replace(receipt, native_file_id="previous-file")
    else:
        altered = replace(receipt, file_version_id="other-operation")
    assert not identity.matches(altered)


@pytest.mark.parametrize("role", ["api", "worker"])
def test_source_composition_resolves_real_admission_when_accounts_are_disabled(role):
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    from koinon.integrations.content_sources.configuration import register_source_accounts
    from koinon.integrations.content_sources.validation_maintenance import SourceValidationMaintenance
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    values = {"koinon": {"process": {"role": role}, "content_sources": {"enabled": False},
                         "operations": {"admission": {"api_capacity": 2}}}}
    context = ApplicationContext(Config(values))
    register_source_accounts(context, values, controllers=role == "api")
    admission = context.get_bean(WorkAdmission)
    assert context.get_bean(WorkAdmissionSettings).api_capacity == 2
    if role == "worker":
        assert context.get_bean(SourceValidationMaintenance).admission is admission
    else:
        assert not context.container.contains_type(SourceValidationMaintenance)


@pytest.mark.parametrize("compressed", [False, True])
async def test_replacement_discovery_reads_bounded_actual_members_and_cleans_scratch(tmp_path, compressed):
    import gzip
    from hashlib import sha256
    from pathlib import Path

    from flyquery.config import FlyquerySettings

    from koinon.integrations.content_sources.sync_replacement import SourceReplacements

    original = b"code,total\nA,1\n"
    content = gzip.compress(original, mtime=0) if compressed else original
    filename = "inventory.csv.gz" if compressed else "inventory.csv"
    settings = FlyquerySettings(ingest_scratch_root=str(tmp_path))
    first = await SourceReplacements.discover(filename, content, settings)
    second = await SourceReplacements.discover(filename, content, settings)
    assert first == second
    assert first.file_format == "csv" and first.compression == ("gz" if compressed else "none")
    assert first.content_sha256 == sha256(content).hexdigest()
    assert len(first.proposed) == 1
    assert first.proposed[0].name == Path(filename).stem
    assert first.proposed[0].sheet_or_json_path is None
    assert first.proposed[0].n_columns == 2 and first.proposed[0].n_rows_estimate == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("change", ["tenant", "owner", "mapping", "run", "policy_revision", "no_item"])
async def test_replacement_rejects_mismatched_execution_before_resolving_dependencies(change):
    from koinon.integrations.content_sources.sync_replacement import SourceReplacements
    from koinon.integrations.content_sources.sync_runs import SourceRunLease
    from koinon.knowledge.bulk.ports import SourceIntakeItem

    pin = SourceIntakeItem("object", 2, "v2", "observation", "work", 1, 0, "a" * 64)
    admission = SourceIntakeAdmission(
        "tenant", "owner", "mapping", 1, 1, "run", ("workspace", "project", "folder"), (pin,)
    )
    execution = SourceRunLease(
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
    fields = {"tenant": "tenant_id", "owner": "owner", "mapping": "mapping_id", "run": "run_id"}
    if change in fields:
        execution = replace(execution, **{fields[change]: "foreign"})
    elif change == "policy_revision":
        execution = replace(execution, mapping_revision=2)
    else:
        admission = replace(admission, items=())
    service = SourceReplacements(None, None, None, None)
    with pytest.raises(ConflictException) as failure:
        await service.execute(admission, execution)
    assert failure.value.code == "SOURCE_REPLACEMENT_CHANGED"


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_new_source_run_clears_the_previous_generation_scan_accounting(empty_listing):
    from koinon.integrations.content_sources.sync_entities import SourceSyncState

    review = empty_listing
    policies, mappings = review.context.get_bean(SourcePolicies), review.context.get_bean(SourceMappings)
    reviewed = await policies.review(
        "issuer|alice", "tenant", "browser-a",
        SourcePolicyReviewInput(**review.request.model_dump(), operation_id=str(uuid4())),
    )
    await policies.apply(
        "issuer|alice", "tenant", "browser-a", reviewed.mapping_id,
        SourcePolicyApplyInput(operation_id=str(uuid4()), expected_revision=1,
                               review_id=reviewed.policy_id, review_digest=reviewed.review_digest),
    )
    async with primary_authority(read_only=False):
        session = review.records._require_session()
        previous = await session.get(SourceSyncState, reviewed.mapping_id)
        previous.scan_max_items, previous.scan_observed_count = 100, 9
        previous.revision += 1
    request = SourceControlInput(operation_id=str(uuid4()), expected_revision=2)
    result = await mappings.execute("issuer|alice", "tenant", reviewed.mapping_id, "sync", request)
    async with primary_authority():
        current = await review.records._require_session().get(SourceSyncState, reviewed.mapping_id)
        assert current.scan_generation == 1
        assert (current.scan_max_items, current.scan_observed_count) == (None, 0)
    assert await mappings.execute("issuer|alice", "tenant", reviewed.mapping_id, "sync", request) == result


@pytest.mark.parametrize("change", [None, "kind", "parent", "scope", "legacy"])
async def test_runtime_file_root_requires_its_reviewed_kind_and_actual_ancestry(
    empty_listing, monkeypatch, change
):
    from koinon.integrations.content_sources.read_authority import source_authority

    review = empty_listing
    mappings = review.context.get_bean(SourceMappings)
    async with primary_authority():
        row = await mappings.connections.connections.owned("tenant", "issuer|alice", review.connection.id)
        authority, digest = source_authority(row)
    mapping = SimpleNamespace(
        provider=row.provider, external_subject=row.external_subject, external_tenant=row.external_tenant,
        connection_id=row.id, drive_id="drive", root_id="selected",
    )
    policy = SimpleNamespace(
        id="policy", policy_sha256="a" * 64, authority_sha256=digest,
        root_ancestry_json=["selected", "root"], policy_json={"authority": authority, "root_kind": "file"},
    )
    if change == "legacy":
        del policy.policy_json["root_kind"]
    original = mappings.browser._source

    @asynccontextmanager
    async def source(scope, tokens):
        async with original(scope, tokens) as adapter:
            get = adapter.get_item

            async def get_item(identifier):
                item = await get(identifier)
                if identifier == "selected":
                    item = replace(item, kind="folder" if change == "kind" else "file")
                    if change == "parent":
                        item = replace(item, parents=("other",))
                    if change == "scope":
                        item = replace(item, scope=SourceScope(scope.account, "foreign"))
                return item

            adapter.get_item = get_item
            yield adapter

    monkeypatch.setattr(mappings.browser, "_source", source)
    if change:
        with pytest.raises(SourceError):
            await mappings.remote_capture("issuer|alice", "tenant", mapping, policy)
    else:
        capture = await mappings.remote_capture("issuer|alice", "tenant", mapping, policy)
        assert capture.connection_revision == row.revision and capture.authority_sha256 == digest


@pytest.fixture
async def producer(empty_listing, monkeypatch, request):
    kind = getattr(request, "param", "file")
    review = empty_listing
    if kind == "dataset":
        review.request = review.request.model_copy(update={"mode": "dataset", "formats": [".csv"]})
    policies, mappings = review.context.get_bean(SourcePolicies), review.context.get_bean(SourceMappings)
    request = SourcePolicyReviewInput(**review.request.model_dump(), operation_id=str(uuid4()))
    result = await policies.review("issuer|alice", "tenant", "browser-a", request)
    await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        result.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=1,
            review_id=result.policy_id,
            review_digest=result.review_digest,
        ),
    )
    run = await mappings.execute(
        "issuer|alice",
        "tenant",
        result.mapping_id,
        "sync",
        SourceControlInput(operation_id=str(uuid4()), expected_revision=1),
    )
    scope = SourceScope(review.connection.account, "drive")
    item = RemoteItem(
        scope,
        "file",
        "Finance" if kind == "folder" else "report.csv" if kind == "dataset" else "report.txt",
        "file" if kind == "dataset" else kind,
        "v1",
        7,
        "text/plain",
        ("selected",),
        True,
    )
    original = mappings.browser._source
    checks = []
    changed = {"version": "v1", "name": item.name, "during": None, "items": {}}

    @asynccontextmanager
    async def remote(scope, tokens):
        async with original(scope, tokens) as adapter:
            original_get = adapter.get_item

            async def get_item(identifier):
                if identifier == item.item_id:
                    _no_remote_unit()
                    return replace(item, version=changed["version"], name=changed["name"])
                if identifier in changed["items"]:
                    return changed["items"][identifier]
                return await original_get(identifier)

            async def check_access(identifier):
                _no_remote_unit()
                if item.kind == "folder" and identifier == item.item_id:
                    raise SourceError("unsupported")
                assert identifier == item.item_id or identifier in changed["items"]
                checks.append(identifier)
                if changed["during"]:
                    await changed["during"]()
                return changed["items"].get(
                    identifier, replace(item, version=changed["version"], name=changed["name"])
                )

            adapter.check_access, adapter.get_item = check_access, get_item
            yield adapter

    monkeypatch.setattr(mappings.browser, "_source", remote)
    authority = review.context.get_bean(BulkAuthority)
    guard = review.context.get_bean(SourceSyncIntake)
    async with primary_authority(read_only=False):
        await authority.destination("issuer|alice", "tenant", request.destination, write=True)
        session = guard._require_session()
        lease = await SourceRunRepository(session=session).claim(
            "tenant", "issuer|alice", run.run_id, "worker"
        )
        from koinon.integrations.content_sources.settings import ContentSourceSettings
        from koinon.integrations.content_sources.sync_entities import SourceSyncState

        # This composition fixture supplies worker admission; worker runtime has its own gate.
        state = await session.get(SourceSyncState, result.mapping_id)
        maximum = review.context.get_bean(ContentSourceSettings).sync_max_scan_items
        state.scan_max_items, state.scan_observed_count = maximum, 0
        state.revision += 1
        await session.flush()
        assert state.scan_max_items == maximum and state.scan_observed_count == 0
        pins = await SourceCheckpoints(session=session).append(
            lease,
            0,
            WalkPage(
                (WalkItem(item, ("selected",)),),
                {"next": True} if kind == "folder" else None,
                kind != "folder",
                1,
            ),
            cursor_ciphertext=b"encrypted" if kind == "folder" else None,
        )
    admission = SourceIntakeAdmission(
        "tenant",
        "issuer|alice",
        result.mapping_id,
        lease.mapping_revision,
        lease.connection_revision,
        run.run_id,
        (request.destination.workspace_id, request.destination.project_id, request.destination.parent_id),
        pins,
    )
    writer = SourcePublicationWriter(guard, authority, SimpleNamespace(get=lambda: mappings))
    return SimpleNamespace(
        review=review,
        guard=guard,
        writer=writer,
        admission=admission,
        checks=checks,
        changed=changed,
        execution=lease,
        remote_item=item,
    )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["folder"], indirect=True)
async def test_folder_creation_publishes_canonical_collection_binding_baseline_and_audit_atomically(producer):
    from sqlalchemy import select

    from koinon.catalog.entities import AuditEvent, CatalogEntry
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.sync_entities import SourceFolderBinding, SourceFolderPublication
    from koinon.integrations.content_sources.sync_folders import SourceFolders

    value = producer
    folders = SourceFolders(value.writer)
    identifier = await folders.publish(value.admission, value.execution)
    assert await folders.publish(value.admission, value.execution) == identifier
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        row = await session.get(CatalogEntry, identifier)
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        publication = (await session.scalars(select(SourceFolderPublication))).one()
        binding = (await session.scalars(select(SourceFolderBinding))).one()
        audits = list(
            (
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.action == "source.folder.published")
                )
            ).all()
        )
        assert (row.kind, row.name, row.parent_id) == (
            "collection",
            "Finance",
            value.admission.destination[2],
        )
        assert binding.local_folder_id == publication.local_folder_id == row.id
        assert origin.state == "imported" and origin.published_native_version_id is None
        assert origin.published_local_revision == str(row.mutation_revision) == "1"
        assert origin.published_sha256 == publication.canonical_sha256
        assert len(audits) == 1 and audits[0].details["publication_id"] == publication.id


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["folder"], indirect=True)
@pytest.mark.parametrize("local_edit", [False, True])
@pytest.mark.parametrize("change", ["rename", "version"])
async def test_folder_rename_keeps_identity_and_rejects_local_aba_edits(producer, local_edit, change):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.sync_entities import SourceFolderPublication
    from koinon.integrations.content_sources.sync_folders import SourceFolders

    value = producer
    folders = SourceFolders(value.writer)
    target = await folders.publish(value.admission, value.execution)
    if local_edit:
        async with primary_authority(read_only=False):
            session = value.guard._require_session()
            for name in ("Local edit", "Finance"):
                await session.execute(update(CatalogEntry).where(CatalogEntry.id == target).values(name=name))
    name, version = ("Accounts", "v1") if change == "rename" else ("Finance", "v2")
    value.changed.update(name=name, version=version)
    async with primary_authority(read_only=False):
        pins = await SourceCheckpoints(session=value.guard._require_session()).append(
            value.execution,
            1,
            WalkPage(
                (WalkItem(replace(value.remote_item, name=name, version=version), ("selected",)),),
                None,
                True,
                1,
            ),
            cursor_ciphertext=None,
        )
    assert pins[0].generation == value.admission.items[0].generation + int(change == "version")
    admission = replace(value.admission, items=pins)
    if local_edit:
        with pytest.raises(ConflictException) as denied:
            await folders.publish(admission, value.execution)
        assert denied.value.code == "SOURCE_FOLDER_CONFLICT"
    else:
        assert await folders.publish(admission, value.execution) == target
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        node = await session.get(CatalogEntry, target)
        ledger = list(
            (
                await session.scalars(
                    select(SourceFolderPublication).order_by(SourceFolderPublication.canonical_revision)
                )
            ).all()
        )
        assert (node.name, node.mutation_revision, len(ledger)) == (
            ("Finance", 3, 1) if local_edit else (name, 2, 2)
        )
        if not local_edit:
            assert ledger[1].previous_publication_id == ledger[0].id


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["folder"], indirect=True)
async def test_folder_audit_failure_rolls_back_canonical_row_and_provenance(producer, monkeypatch):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.sync_entities import SourceFolderBinding, SourceFolderPublication
    from koinon.integrations.content_sources.sync_folders import SourceFolders

    value = producer
    catalog = value.writer.authority.catalog
    original = catalog._audit

    async def audit(subject, tenant, action, target, details):
        if action == "source.folder.published":
            raise RuntimeError("Audit unavailable")
        await original(subject, tenant, action, target, details)

    monkeypatch.setattr(catalog, "_audit", audit)
    with pytest.raises(RuntimeError, match="Audit unavailable"):
        await SourceFolders(value.writer).publish(value.admission, value.execution)
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        assert await session.scalar(select(CatalogEntry.id).where(CatalogEntry.name == "Finance")) is None
        assert await session.scalar(select(SourceFolderPublication.id)) is None
        assert await session.scalar(select(SourceFolderBinding.local_folder_id)) is None


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["folder"], indirect=True)
@pytest.mark.parametrize("local_child", [False, True, "managed"])
async def test_source_folder_move_reuses_domain_rules_and_rejects_local_descendants(producer, local_child):
    from sqlalchemy import select

    from koinon.catalog.entities import AuditEvent, CatalogEntry
    from koinon.integrations.content_sources.sync_entities import SourceFolderPublication
    from koinon.integrations.content_sources.sync_folders import SourceFolders

    value = producer
    folders = SourceFolders(value.writer)
    target = await folders.publish(value.admission, value.execution)
    destination = replace(value.remote_item, item_id="destination", name="Target")
    value.changed["items"]["destination"] = destination
    async with primary_authority(read_only=False):
        pins = await SourceCheckpoints(session=value.guard._require_session()).append(
            value.execution,
            1,
            WalkPage((WalkItem(destination, ("selected",)),), {"next": True}, False, 1),
            cursor_ciphertext=b"next",
        )
    parent = await folders.publish(replace(value.admission, items=pins), value.execution)
    next_page = 2
    child = None
    if local_child is True:
        async with primary_authority(read_only=False):
            value.guard._require_session().add(
                CatalogEntry(
                    id=str(uuid4()),
                    tenant_id="tenant",
                    kind="collection",
                    name="Local child",
                    parent_id=target,
                    workspace_id=value.admission.destination[0],
                    project_id=value.admission.destination[1],
                    created_by="issuer|alice",
                )
            )
    elif local_child == "managed":
        child = replace(value.remote_item, item_id="child", name="Managed child", parents=("file",))
        value.changed["items"].update({"file": value.remote_item, "child": child})
        async with primary_authority(read_only=False):
            child_pins = await SourceCheckpoints(session=value.guard._require_session()).append(
                value.execution,
                2,
                WalkPage((WalkItem(child, ("selected", "file")),), {"next": True}, False, 1),
                cursor_ciphertext=b"child",
            )
        child_id = await folders.publish(
            replace(
                value.admission, items=child_pins, destination=(*value.admission.destination[:2], target)
            ),
            value.execution,
        )
        next_page = 3
    moved = replace(value.remote_item, parents=("destination",))
    value.changed["items"][moved.item_id] = moved
    observations = (WalkItem(moved, ("selected", "destination")),)
    if child is not None:
        observations += (WalkItem(child, ("selected", "destination", "file")),)
    async with primary_authority(read_only=False):
        pins = await SourceCheckpoints(session=value.guard._require_session()).append(
            value.execution,
            next_page,
            WalkPage(observations, None, True, len(observations)),
            cursor_ciphertext=None,
        )
    admission = replace(value.admission, items=pins, destination=(*value.admission.destination[:2], parent))
    if local_child is True:
        with pytest.raises(ConflictException):
            await folders.publish(admission, value.execution)
    else:
        assert await folders.publish(admission, value.execution) == target
    if child is not None:
        child_admission = replace(
            value.admission, items=(pins[1],), destination=(*value.admission.destination[:2], target)
        )
        assert await folders.publish(child_admission, value.execution) == child_id
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        row = await session.get(CatalogEntry, target)
        assert row.parent_id == (value.admission.destination[2] if local_child is True else parent)
        if child is not None:
            assert (await session.get(CatalogEntry, child_id)).parent_id == target
        ledger = list(
            (
                await session.scalars(
                    select(SourceFolderPublication).where(SourceFolderPublication.local_folder_id == target)
                )
            ).all()
        )
        assert len(ledger) == (1 if local_child is True else 2)
        audits = list(
            (await session.scalars(select(AuditEvent).where(AuditEvent.action == "catalog.moved"))).all()
        )
        assert len(audits) == (0 if local_child is True else 1)
        if local_child is not True:
            assert audits[0].details == {
                "from_parent_id": value.admission.destination[2],
                "to_parent_id": parent,
            }


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_new_accepted_policy_advances_generation_without_reviving_cancelled_run(producer):
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.sync_entities import SourceSyncState

    value = producer
    mappings = value.review.context.get_bean(SourceMappings)
    policies = value.review.context.get_bean(SourcePolicies)
    async with primary_authority(read_only=True):
        current = await value.guard._require_session().get(SourceSyncState, value.admission.mapping_id)
        revision = current.revision
    await mappings.execute(
        "issuer|alice",
        "tenant",
        value.admission.mapping_id,
        "cancel",
        SourceControlInput(operation_id=str(uuid4()), expected_revision=revision),
        target_run_id=value.admission.run_id,
    )
    async with primary_authority(read_only=False):
        assert await SourceRunRepository(session=value.guard._require_session()).finish(value.execution)
    selected = SourcePolicyReviewInput(
        **{**value.review.request.model_dump(), "hierarchy": "flatten"}, operation_id=str(uuid4())
    )
    review = await policies.review(
        "issuer|alice",
        "tenant",
        "browser-a",
        selected,
        mapping_id=value.admission.mapping_id,
        expected_revision=1,
    )
    await policies.apply(
        "issuer|alice",
        "tenant",
        "browser-a",
        value.admission.mapping_id,
        SourcePolicyApplyInput(
            operation_id=str(uuid4()),
            expected_revision=2,
            review_id=review.policy_id,
            review_digest=review.review_digest,
        ),
    )
    async with primary_authority(read_only=True):
        revision = (
            await value.guard._require_session().get(SourceSyncState, value.admission.mapping_id)
        ).revision
    scheduled = await mappings.execute(
        "issuer|alice",
        "tenant",
        value.admission.mapping_id,
        "sync",
        SourceControlInput(operation_id=str(uuid4()), expected_revision=revision),
    )
    async with primary_authority(read_only=False):
        session = value.guard._require_session()
        execution = await SourceRunRepository(session=session).claim(
            "tenant", "issuer|alice", scheduled.run_id, "new-worker"
        )
        pins = await SourceCheckpoints(session=session).append(
            execution,
            0,
            WalkPage((WalkItem(value.remote_item, ("selected",)),), None, True, 1),
            cursor_ciphertext=None,
        )
        origin = await session.get(SourceObject, pins[0].object_id)
        assert origin.generation == 2 and origin.mapping_revision == 2
        assert pins[0].work_id != value.admission.items[0].work_id
        with pytest.raises(ConflictException):
            await value.guard._fence(value.admission)


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_actual_provider_preparation_and_catalog_create_share_short_fence(producer):
    value = producer
    catalog = value.review.context.get_bean(CatalogService)
    target = str(uuid4())
    changes = dict(kind="source", name="Imported file", description="", metadata={})
    operation = SourceWriteOperation("create", target, value.admission.destination[2], changes)
    async with (
        value.writer.prepare(value.admission, execution=value.execution),
        primary_authority(read_only=False),
        value.writer.fence(value.admission),
    ):
        async with value.writer.open(value.admission, (operation,)) as permit:
            created = await catalog.create(
                "issuer|alice",
                "tenant",
                **changes,
                parent_id=value.admission.destination[2],
                _source_create_id=target,
                _source_write=permit,
            )
            assert created.id == target
        with pytest.raises(ConflictException):
            async with value.writer.fence(value.admission):
                pytest.fail("One provider preparation cannot authorize another publication")
    assert value.checks == ["file"]


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("foreign_version", [False, True])
async def test_private_creation_and_version_merge_preserve_unrelated_metadata(producer, foreign_version):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry

    value = producer
    catalog = value.writer.authority.catalog
    source, version = str(uuid4()), str(uuid4())
    version_parent = value.admission.destination[2] if foreign_version else source
    source_values = dict(kind="source", name="Source", description="", metadata={"retained": "unchanged"})
    version_values = dict(kind="index_version", name="Version", description="", metadata={})
    operations = (
        SourceWriteOperation("create", source, value.admission.destination[2], source_values),
        SourceWriteOperation("create", version, version_parent, version_values),
        SourceWriteOperation(
            "merge_latest", source, value.admission.destination[2], {"latest_content_version_id": version}, 1
        ),
    )
    from contextlib import nullcontext

    expected = pytest.raises(ConflictException) if foreign_version else nullcontext()
    with expected:
        async with (
            value.writer.prepare(value.admission, execution=value.execution),
            primary_authority(read_only=False),
            value.writer.fence(value.admission),
            value.writer.open(value.admission, operations) as permit,
        ):
            await catalog.create(
                "issuer|alice",
                "tenant",
                **source_values,
                parent_id=value.admission.destination[2],
                _source_create_id=source,
                _source_write=permit,
            )
            await catalog.create(
                "issuer|alice",
                "tenant",
                **version_values,
                parent_id=version_parent,
                _source_create_id=version,
                _source_write=permit,
            )
            state = await catalog._merge_latest(
                "issuer|alice",
                "tenant",
                source,
                version,
                _source_parent_id=value.admission.destination[2],
                _source_write=permit,
            )
            assert state.latest_content_version_id == version and state.mutation_revision == 2
    if foreign_version:
        return
    async with primary_authority(read_only=True):
        metadata = await value.guard._require_session().scalar(
            select(CatalogEntry.metadata_json).where(CatalogEntry.id == source)
        )
        assert metadata == {"retained": "unchanged", "latest_content_version_id": version}
    with pytest.raises(ConflictException):
        await catalog._merge_latest("issuer|alice", "tenant", source, version)


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("change", ["remote_version", "local_revoke"])
async def test_changed_provider_or_membership_prevents_publication(producer, change):
    value = producer
    if change == "remote_version":
        value.changed["version"] = "v2"
    else:

        async def revoke():
            async with primary_authority(read_only=False):
                await value.guard._require_session().execute(
                    update(Membership).where(Membership.id == "issuer|alice").values(role="viewer")
                )

        value.changed["during"] = revoke
    with pytest.raises((ConflictException, AccessDenied)):
        async with (
            value.writer.prepare(value.admission, execution=value.execution),
            primary_authority(read_only=False),
            value.writer.fence(value.admission),
        ):
            pytest.fail("Revocation must prevent source publication")


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("change", ["expired", "foreign_job", "takeover_during_provider"])
async def test_source_writer_rejects_expired_foreign_or_replaced_execution(producer, change):
    from dataclasses import replace

    value = producer
    execution = value.execution
    if change == "foreign_job":
        execution = replace(execution, job_id=str(uuid4()))
    elif change == "expired":
        async with primary_authority(read_only=False):
            await value.guard._require_session().execute(
                update(Job)
                .where(Job.id == execution.job_id)
                .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
            )
    else:

        async def takeover():
            async with primary_authority(read_only=False):
                await value.guard._require_session().execute(
                    update(Job)
                    .where(Job.id == execution.job_id)
                    .values(worker_id="replacement-worker", attempts=execution.attempt + 1)
                )

        value.changed["during"] = takeover
    with pytest.raises(ConflictException):
        async with (
            value.writer.prepare(value.admission, execution=execution),
            primary_authority(read_only=False),
            value.writer.fence(value.admission),
        ):
            pytest.fail("Stale or unrelated execution cannot acquire publication authority")
    assert value.checks == (["file"] if change == "takeover_during_provider" else [])


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_execution_expiry_before_commit_rolls_back_canonical_write(producer):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry

    value = producer
    catalog = value.review.context.get_bean(CatalogService)
    target = str(uuid4())
    changes = dict(kind="source", name="Never published", description="", metadata={})
    operation = SourceWriteOperation("create", target, value.admission.destination[2], changes)
    with pytest.raises(ConflictException):
        async with (
            value.writer.prepare(value.admission, execution=value.execution),
            primary_authority(read_only=False),
            value.writer.fence(value.admission),
            value.writer.open(value.admission, (operation,)) as permit,
        ):
            await catalog.create(
                "issuer|alice",
                "tenant",
                **changes,
                parent_id=value.admission.destination[2],
                _source_create_id=target,
                _source_write=permit,
            )
            await value.guard._require_session().execute(
                update(Job)
                .where(Job.id == value.execution.job_id)
                .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
            )
    async with primary_authority(read_only=True):
        assert (
            await value.guard._require_session().scalar(
                select(CatalogEntry.id).where(CatalogEntry.id == target)
            )
            is None
        )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_committed_receipt_settles_after_membership_revocation_without_catalog_publication(producer):
    from dataclasses import asdict
    from unittest.mock import AsyncMock

    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import select

    from koinon.catalog.entities import AuditEvent, CatalogEntry
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.sync_entities import SourceSyncWork
    from koinon.jobs.entities import Job
    from koinon.knowledge.bulk.entities import BulkBatch, BulkItem
    from koinon.knowledge.bulk.native import NativeBulkIntake
    from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation
    from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
    from koinon.knowledge.bulk.repositories import BulkRepository
    from koinon.knowledge.bulk.settings import BulkSettings

    value = producer
    catalog = value.review.context.get_bean(CatalogService)
    source = await catalog.create(
        "issuer|alice",
        "tenant",
        kind="source",
        name="Retained source",
        parent_id=value.admission.destination[2],
        metadata={"sha256": "d" * 64},
    )
    asset = await catalog.create(
        "issuer|alice",
        "tenant",
        kind="document",
        name="Retained asset",
        parent_id=source.id,
        metadata={"sha256": "d" * 64},
    )
    records = value.review.context.get_bean(BulkRepository)
    batch_id, item_id, job_id = (str(uuid4()) for _ in range(3))
    async with primary_authority(read_only=False):
        session = value.guard._require_session()
        session.add(
            BulkBatch(
                id=batch_id,
                tenant_id="tenant",
                subject="issuer|alice",
                workspace_id=source.workspace_id,
                project_id=source.project_id,
                parent_id=source.parent_id,
                key_hash="d" * 64,
                request_hash="e" * 64,
                request_json={"_source_admission": asdict(value.admission)},
                total_bytes=7,
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        session.add(
            Job(
                id=job_id,
                tenant_id="tenant",
                resource_id=item_id,
                kind="knowledge.bulk.intake",
                idempotency_key=job_id,
                payload_hash="f" * 64,
                payload={},
                status="running",
            )
        )
        await session.flush()
        item = BulkItem(
            id=item_id,
            batch_id=batch_id,
            ordinal=0,
            client_item_id="file",
            filename="report.txt",
            mode="document",
            size_bytes=7,
            sha256="d" * 64,
            source_id=source.id,
            asset_id=asset.id,
            status="running",
            native_workspace_id="native-space",
            job_id=job_id,
        )
        session.add(item)
        await session.flush()
        await value.guard.admit(value.admission)
        await value.guard.bind(value.admission, 0, item)
        await session.execute(update(Membership).where(Membership.id == "issuer|alice").values(role="viewer"))
    lease = BulkLease(
        job_id,
        item_id,
        batch_id,
        "tenant",
        "issuer|alice",
        None,
        "worker",
        1,
        source.id,
        asset.id,
        "report.txt",
        7,
        "d" * 64,
        "document",
        value.review.request.destination,
    )
    queue = BulkQueue(
        records,
        value.writer.authority,
        BulkSettings(),
        value.review.context.get_bean(DataSourceRegistry),
        SimpleNamespace(get=lambda: value.guard),
    )
    port = NativeBulkIntake(
        SimpleNamespace(get=lambda: pytest.fail("Receipt settlement cannot hydrate a facade")), records, queue
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
    port.inspect_committed = AsyncMock(return_value=NativeObservation("committed", receipt))
    with pytest.raises(AccessDenied):
        await port.acknowledge_committed(lease, receipt)
    port.inspect_committed.assert_not_awaited()
    calls = len(value.review.state.calls)
    await port.settle_source_receipt(lease, receipt)
    await port.settle_source_receipt(lease, receipt)
    assert len(value.review.state.calls) == calls
    async with primary_authority():
        session = value.guard._require_session()
        assert (await session.get(BulkItem, item_id)).status == "succeeded"
        assert (await session.get(Job, job_id)).status == "succeeded"
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        assert origin.state == "pending" and origin.published_native_version_id is None
        assert (await session.get(SourceSyncWork, value.admission.items[0].work_id)).status == "imported"
        assert (await session.get(CatalogEntry, source.id)).mutation_revision == source.mutation_revision
        assert (await session.get(CatalogEntry, asset.id)).mutation_revision == asset.mutation_revision
        audit = list(
            (
                await session.scalars(
                    select(AuditEvent).where(AuditEvent.action == "knowledge.source.receipt_recorded")
                )
            ).all()
        )
        assert len(audit) == 1 and audit[0].resource_id == item_id


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["file", "dataset"], indirect=True)
async def test_source_file_admission_commits_owned_catalog_and_attempt_without_reader_access(
    producer, source_files, tmp_path
):
    from hashlib import sha256

    from sqlalchemy import func, select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.sync_entities import SourceImportedAsset, SourceSyncWork
    from koinon.knowledge.bulk.dtos import FileBatchCreate
    from koinon.knowledge.bulk.entities import BulkItem

    value = producer
    catalog, files = value.writer.authority.catalog, source_files
    mode = value.review.request.mode
    payload = FileBatchCreate.model_validate(
        {
            "destination": dict(
                zip(("workspace_id", "project_id", "parent_id"), value.admission.destination, strict=True)
            ),
            "items": [
                {
                    "client_item_id": "file",
                    "filename": value.remote_item.name,
                    "mode": mode,
                    "size_bytes": 7,
                    "sha256": sha256(b"source!").hexdigest(),
                }
            ],
        }
    )
    result = await files.create(
        "issuer|alice",
        "tenant",
        payload,
        "source-file",
        _source_admission=value.admission,
        _source_execution=value.execution,
    )
    replay = await files.create(
        "issuer|alice",
        "tenant",
        payload,
        "source-file",
        _source_admission=value.admission,
        _source_execution=value.execution,
    )
    assert result.id == replay.id and result.counts == {"awaiting_upload": 1}
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        attempt = await session.scalar(select(SourceImportAttempt))
        item = await session.scalar(select(BulkItem).where(BulkItem.batch_id == result.id))
        marker = await session.get(SourceImportedAsset, item.asset_id)
        assert (attempt.intake_item_id, attempt.source_id, attempt.asset_id) == (
            item.id,
            item.source_id,
            item.asset_id,
        )
        assert marker.initial_attempt_id == attempt.id
        assert (await session.get(SourceSyncWork, value.admission.items[0].work_id)).attempt_id == attempt.id
        assert (await session.get(CatalogEntry, item.source_id)).status == "pending"
        assert (await session.get(CatalogEntry, item.asset_id)).status == "pending"
        assert await session.scalar(select(func.count()).select_from(SourceImportAttempt)) == 1
        assert bool(item.reservation_json) == (mode == "dataset")
    original_path = tmp_path / "downloaded-original"
    original_path.write_bytes(b"source!")
    receipt = await files.stage(
        "issuer|alice",
        "tenant",
        result.id,
        item.id,
        original_path,
        "source-upload",
        _source_admission=value.admission,
        _source_execution=value.execution,
    )
    replay_receipt = await files.stage(
        "issuer|alice",
        "tenant",
        result.id,
        item.id,
        b"source!",
        "source-upload",
        _source_admission=value.admission,
        _source_execution=value.execution,
    )
    assert receipt == replay_receipt and receipt.sha256 == sha256(b"source!").hexdigest()
    async with primary_authority(read_only=True):
        stored = await value.writer.authority.records.item(result.id, item.id)
        upload = await value.writer.authority.records.upload_by_id(stored.winning_upload_id)
        assert stored.status == "staged" and upload.status == "verified"
    assert await files.storage.read(upload.object_key, 7, receipt.sha256) == b"source!"
    from koinon.knowledge.bulk.dtos import BulkAction

    submitted = await files.submit(
        "issuer|alice",
        "tenant",
        result.id,
        BulkAction(expected_revision=2),
        "submit-source",
        _source_admission=value.admission,
        _source_execution=value.execution,
    )
    replay_submit = await files.submit(
        "issuer|alice",
        "tenant",
        result.id,
        BulkAction(expected_revision=2),
        "submit-source",
        _source_admission=value.admission,
        _source_execution=value.execution,
    )
    assert submitted.id == replay_submit.id and submitted.counts == {"queued": 1}
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        jobs = list((await session.scalars(select(Job).where(Job.kind == "knowledge.bulk.intake"))).all())
        assert len(jobs) == 1 and jobs[0].resource_id == item.asset_id
    from koinon.knowledge.bulk.queue import BulkQueue

    async with primary_authority(read_only=False):
        claimed = await files.records.claim("bulk-worker", 360, 4, 4)
        assert claimed is not None
        bulk_execution = BulkQueue._lease(*claimed)
    async with (
        value.writer.prepare(value.admission, execution=bulk_execution),
        primary_authority(read_only=False),
        value.writer.fence(value.admission),
    ):
        assert bulk_execution.item_id == item.id
    from koinon.knowledge.bulk.settings import BulkSettings

    queue = BulkQueue(
        files.records,
        files.authority,
        BulkSettings(),
        None,
        source_fences=SimpleNamespace(get=lambda: value.guard),
    )
    queue.source_writers = SimpleNamespace(get=lambda: value.writer)
    await queue.check(bulk_execution)
    original = await queue.original(bulk_execution)
    assert original.sha256 == payload.items[0].sha256 and original.size_bytes == 7
    catalog.get.assert_not_called()


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("failure", ["unused", "swallowed"])
async def test_partial_or_invalidated_publication_cannot_commit_any_catalog_write(producer, failure):
    from koinon.catalog.entities import CatalogEntry

    value = producer
    target, extra = str(uuid4()), str(uuid4())
    changes = dict(kind="source", name="Incomplete", description="", metadata={})
    operations = (
        SourceWriteOperation("create", target, value.admission.destination[2], changes),
        SourceWriteOperation("create", extra, value.admission.destination[2], changes),
    )
    with pytest.raises(ConflictException):
        async with (
            value.writer.prepare(value.admission, execution=value.execution),
            primary_authority(read_only=False),
            value.writer.fence(value.admission),
            value.writer.open(value.admission, operations) as permit,
        ):
            catalog = value.writer.authority.catalog
            await catalog.create(
                "issuer|alice",
                "tenant",
                **changes,
                parent_id=value.admission.destination[2],
                _source_create_id=target,
                _source_write=permit,
            )
            if failure == "swallowed":
                with pytest.raises(ConflictException):
                    await catalog.create(
                        "issuer|alice",
                        "tenant",
                        **{**changes, "name": "Changed"},
                        parent_id=value.admission.destination[2],
                        _source_create_id=extra,
                        _source_write=permit,
                    )
    async with primary_authority(read_only=True):
        assert await value.guard._require_session().get(CatalogEntry, target) is None


@pytest.fixture
async def source_files(producer, tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    from pyfly.core import Config

    from koinon.jobs.service import JobService
    from koinon.knowledge.bulk.service import FileBatches
    from koinon.knowledge.bulk.settings import BulkSettings
    from koinon.knowledge.bulk.storage import BulkStorage
    from koinon.storage.scratch import ScratchAdmission

    root = tmp_path / "private"
    root.mkdir(mode=0o700)
    settings = BulkSettings(storage_root=str(root))
    storage = BulkStorage(settings, ScratchAdmission(Config({})))
    value = producer
    await configure_source_embedding(value, value.review.request.mode)
    catalog = value.writer.authority.catalog
    monkeypatch.setattr(
        catalog, "get", AsyncMock(side_effect=AssertionError("Source staging cannot read protected output"))
    )
    try:
        yield FileBatches(
            catalog,
            value.writer.authority.records,
            storage,
            settings,
            value.review.context.get_bean(JobService),
            value.writer.authority,
            source_guards=SimpleNamespace(get=lambda: value.guard),
            source_writers=SimpleNamespace(get=lambda: value.writer),
        )
    finally:
        await storage.close()


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("change", [{"mode": "dataset"}, {"filename": "other.txt"}, {"size_bytes": 8}])
async def test_source_file_manifest_must_match_accepted_policy_and_observation(
    producer, source_files, change
):
    from sqlalchemy import func, select

    from koinon.catalog.entities import CatalogEntry
    from koinon.knowledge.bulk.dtos import FileBatchCreate
    from koinon.knowledge.bulk.entities import BulkBatch

    value = producer
    request = FileBatchCreate.model_validate(
        {
            "destination": dict(
                zip(("workspace_id", "project_id", "parent_id"), value.admission.destination, strict=True)
            ),
            "items": [
                {
                    "client_item_id": "one",
                    "filename": "report.txt",
                    "mode": "document",
                    "sha256": "a" * 64,
                    "size_bytes": 7,
                    **change,
                }
            ],
        }
    )
    with pytest.raises(ConflictException):
        await source_files.create(
            "issuer|alice",
            "tenant",
            request,
            "wrong-manifest",
            _source_admission=value.admission,
            _source_execution=value.execution,
        )
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        assert await session.scalar(select(func.count()).select_from(BulkBatch)) == 0
        assert (
            await session.scalar(
                select(func.count()).select_from(CatalogEntry).where(CatalogEntry.kind == "source")
            )
            == 0
        )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("change", ["lease", "remote", "membership"])
async def test_source_transfer_authority_change_retains_bytes_without_publishing_receipt(
    producer, source_files, monkeypatch, change
):
    from hashlib import sha256

    from sqlalchemy import select

    from koinon.knowledge.bulk.dtos import FileBatchCreate
    from koinon.knowledge.bulk.entities import BulkItem, BulkUpload

    value = producer
    payload = FileBatchCreate.model_validate(
        {
            "destination": dict(
                zip(("workspace_id", "project_id", "parent_id"), value.admission.destination, strict=True)
            ),
            "items": [
                {
                    "client_item_id": "one",
                    "filename": "report.txt",
                    "mode": "document",
                    "size_bytes": 7,
                    "sha256": sha256(b"source!").hexdigest(),
                }
            ],
        }
    )
    batch = await source_files.create(
        "issuer|alice",
        "tenant",
        payload,
        "transfer-change",
        _source_admission=value.admission,
        _source_execution=value.execution,
    )
    async with primary_authority(read_only=True):
        item = await value.guard._require_session().scalar(
            select(BulkItem).where(BulkItem.batch_id == batch.id)
        )
    original_put = source_files.storage.put

    async def changed_put(*args):
        _no_remote_unit()
        result = await original_put(*args)
        if change == "remote":
            value.changed["version"] = "v2"
        else:
            async with primary_authority(read_only=False):
                session = value.guard._require_session()
                if change == "lease":
                    await session.execute(
                        update(Job)
                        .where(Job.id == value.execution.job_id)
                        .values(lease_until=datetime.now(UTC) - timedelta(seconds=1))
                    )
                else:
                    await session.execute(
                        update(Membership).where(Membership.subject == "issuer|alice").values(role="viewer")
                    )
        return result

    monkeypatch.setattr(source_files.storage, "put", changed_put)
    with pytest.raises((ConflictException, AccessDenied)):
        await source_files.stage(
            "issuer|alice",
            "tenant",
            batch.id,
            item.id,
            b"source!",
            "transfer",
            _source_admission=value.admission,
            _source_execution=value.execution,
        )
    async with primary_authority(read_only=True):
        session = value.guard._require_session()
        stored = await session.get(BulkItem, item.id)
        upload = await session.scalar(select(BulkUpload).where(BulkUpload.item_id == item.id))
        assert stored.winning_upload_id is None and stored.status == "awaiting_upload"
        assert upload.status == "uncertain" and not upload.permit_held
    assert await source_files.storage.read(upload.object_key, 7, payload.items[0].sha256) == b"source!"


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("receipt_change", [None, "digest", "identity"])
async def test_provider_download_receipt_must_match_measured_bytes_before_intake(
    producer, source_files, monkeypatch, receipt_change
):
    from hashlib import sha256

    from sqlalchemy import func, select

    from koinon.integrations.content_sources.dtos import DownloadReceipt
    from koinon.integrations.content_sources.sync_files import SourceFiles
    from koinon.knowledge.bulk.entities import BulkBatch

    value = producer
    mappings = value.review.context.get_bean(SourceMappings)
    original = mappings.browser._source

    @asynccontextmanager
    async def remote(scope, token):
        async with original(scope, token) as adapter:

            async def download(item, sink, *, max_bytes, export_mime):
                _no_remote_unit()
                await sink.write(b"source!")
                return DownloadReceipt(
                    scope,
                    "other" if receipt_change == "identity" else item.item_id,
                    item.version,
                    7,
                    "0" * 64 if receipt_change == "digest" else sha256(b"source!").hexdigest(),
                    item.mime_type,
                )

            adapter.download = download
            yield adapter

    monkeypatch.setattr(mappings.browser, "_source", remote)
    files = SourceFiles(value.writer, mappings, SimpleNamespace(get=lambda: source_files))
    if receipt_change is None:
        result = await files.intake(value.admission, value.execution)
        async with primary_authority(read_only=True):
            session = value.guard._require_session()
            job = await session.get(Job, result.job_id)
            assert job.kind == "knowledge.bulk.intake" and job.status == "queued"
            assert job.payload == {"batch_id": result.batch_id, "item_id": result.item_id}
    else:
        with pytest.raises(ConflictException):
            await files.intake(value.admission, value.execution)
        async with primary_authority(read_only=True):
            assert (
                await value.guard._require_session().scalar(select(func.count()).select_from(BulkBatch)) == 0
            )
    assert source_files.storage.scratch.available_bytes == source_files.storage.scratch.capacity_bytes


async def configure_source_embedding(value, mode):
    from koinon.assistants.entities import Provider
    from koinon.knowledge.connections.entities import KnowledgeConnection

    async with primary_authority(read_only=False):
        session = value.guard._require_session()
        session.add(
            Provider(
                id="embedding",
                tenant_id="tenant",
                name="Inert",
                kind="ollama",
                base_url="http://unresolved.invalid",
                model_ids=["embedding"],
                enabled=True,
                revision=1,
                validated_revision=1,
            )
        )
        session.add(
            KnowledgeConnection(
                id="embedding",
                tenant_id="tenant",
                workspace_id=value.admission.destination[0],
                scope_key=value.admission.destination[0],
                domain="documents" if mode == "document" else "structured",
                role="documents.embedding" if mode == "document" else "structured.embedding",
                mode="provider",
                provider_id="embedding",
                model_id="embedding",
                dimensions=768,
                embedding_fingerprint="f" * 64,
                created_by="issuer|alice",
                updated_by="issuer|alice",
            )
        )


@pytest.fixture
async def claimed_source_file(producer, source_files):
    from hashlib import sha256

    from sqlalchemy import select

    from koinon.knowledge.bulk.dtos import BulkAction, FileBatchCreate
    from koinon.knowledge.bulk.entities import BulkItem
    from koinon.knowledge.bulk.queue import BulkQueue
    from koinon.knowledge.bulk.settings import BulkSettings
    from koinon.knowledge.entities import DomainBinding

    value, files = producer, source_files
    content = b"a\n1\n22\n" if value.review.request.mode == "dataset" else b"source!"
    native_workspace = str(uuid4()) if value.review.request.mode == "dataset" else "source-native-workspace"
    private = dict(_source_admission=value.admission, _source_execution=value.execution)
    manifest = FileBatchCreate.model_validate(
        {
            "destination": value.review.request.destination.model_dump(),
            "items": [
                {
                    "client_item_id": "file",
                    "filename": value.remote_item.name,
                    "mode": value.review.request.mode,
                    "size_bytes": 7,
                    "sha256": sha256(content).hexdigest(),
                }
            ],
        }
    )
    batch = await files.create("issuer|alice", "tenant", manifest, "source-ack", **private)
    async with primary_authority():
        item_id = await value.guard._require_session().scalar(
            select(BulkItem.id).where(BulkItem.batch_id == batch.id)
        )
    await files.stage("issuer|alice", "tenant", batch.id, item_id, content, "upload", **private)
    await files.submit(
        "issuer|alice", "tenant", batch.id, BulkAction(expected_revision=2), "submit", **private
    )
    async with primary_authority(read_only=False):
        claimed = await files.records.claim("source-native", 360, 4, 4)
        assert claimed is not None
        lease = BulkQueue._lease(*claimed)
        claimed[1].native_workspace_id = native_workspace
        value.guard._require_session().add(
            DomainBinding(
                id=str(uuid4()),
                tenant_id="tenant",
                catalog_id=lease.destination.workspace_id,
                workspace_id=lease.destination.workspace_id,
                domain="structured" if lease.mode == "dataset" else "canon",
                entity_kind="workspace",
                native_id=native_workspace,
                native_workspace_id=native_workspace,
                created_by=lease.subject,
            )
        )
    queue = BulkQueue(
        files.records,
        files.authority,
        BulkSettings(),
        None,
        source_fences=SimpleNamespace(get=lambda: value.guard),
        source_writers=SimpleNamespace(get=lambda: value.writer),
    )
    return SimpleNamespace(
        producer=value,
        files=files,
        queue=queue,
        lease=lease,
        content=content,
        native_workspace=native_workspace,
    )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_source_native_acknowledgement_publishes_and_completes_the_claimed_job_atomically(
    claimed_source_file,
):
    import json
    from dataclasses import asdict

    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
    from koinon.integrations.content_sources.sync_entities import SourceImportedVersion
    from koinon.knowledge.bulk.entities import BulkItem

    current = claimed_source_file
    value, lease = current.producer, current.lease
    port, receipt = await source_ack_port(current)
    await port.acknowledge(lease, receipt)
    async with primary_authority():
        session = value.guard._require_session()
        item = await session.get(BulkItem, lease.item_id)
        job = await session.get(Job, lease.job_id)
        attempt = await session.scalar(select(SourceImportAttempt))
        version = await session.get(SourceImportedVersion, attempt.id)
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        assert item.receipt_json == attempt.receipt_json == json.loads(json.dumps(asdict(receipt)))
        assert item.status == job.status == "succeeded"
        assert job.worker_id is None and job.lease_until is None and job.attempts == lease.attempt
        assert version.native_version_id == origin.published_native_version_id == "native-version"
        baseline = await session.get(SourcePublicationBaseline, attempt.id)
        assert baseline.acknowledgement_json is not None
        assert origin.published_local_revision == "cpv1:" + baseline.acknowledgement_sha256
        assert (await session.get(CatalogEntry, lease.source_id)).status == "ready"
        assert (await session.get(CatalogEntry, lease.asset_id)).status == "ready"
    port.facade().catalog.get.assert_not_called()


async def source_ack_port(current, *, members=()):
    from unittest.mock import AsyncMock

    from koinon.knowledge.bulk.native import NativeBulkIntake
    from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

    value, lease = current.producer, current.lease
    binding = None
    if lease.mode == "document" or members:
        async with current.queue.publication(lease) as admission:
            binding = await value.writer.freeze_publication(admission, execution=lease, members=members)
    facade = KnowledgeFacade(
        value.writer.authority.catalog, DomainBindingRepository(), SimpleNamespace(), KnowledgeSettings()
    )
    port = NativeBulkIntake(SimpleNamespace(get=lambda: facade), current.files.records, current.queue)
    receipt = NativeCommit(
        "canon",
        "source-native-workspace",
        "native-source",
        "native-source",
        lease.sha256,
        lease.size_bytes,
        source_version_id="native-version",
        extraction_id="native-extraction",
        n_chunks=1,
        source_attempt_id=binding.attempt_id if binding else None,
        source_publication_sha256=binding.descriptor_sha256 if binding else None,
    )

    async def committed(_):
        _no_remote_unit()
        return NativeObservation("committed", receipt)

    port.inspect_committed = AsyncMock(side_effect=committed)
    return port, receipt


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("fault", ["result", "attempt", "duplicate", "expired", "cancelled", "receipt"])
async def test_source_native_acknowledgement_rejects_changed_terminal_proof_and_rolls_back(
    claimed_source_file,
    monkeypatch,
    fault,
):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources import source_publication
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.sync_entities import SourceImportedVersion, SourceSyncRun
    from koinon.knowledge.bulk.entities import BulkItem

    current = claimed_source_file
    value, lease = current.producer, current.lease
    port, receipt = await source_ack_port(current)
    original = port._record_success

    async def interrupted(execution, committed, job, item, batch):
        if fault == "receipt":
            committed = replace(committed, extraction_id="different-extraction")
        await original(execution, committed, job, item, batch)
        if fault == "result":
            job.result = {**job.result, "asset_id": "different-asset"}
        elif fault == "attempt":
            job.attempts += 1
        elif fault == "duplicate":
            session = value.guard._require_session()
            admission = next(iter(session.info["source_publication_fences"].values()))[1]
            with pytest.raises(ConflictException):
                async with value.writer.completion(admission, execution, committed):
                    pytest.fail("A second completion cannot enter")
        elif fault == "expired":

            class ExpiredClock:
                @staticmethod
                def now(_):
                    return datetime.now(UTC) + timedelta(hours=1)

            monkeypatch.setattr(source_publication, "datetime", ExpiredClock)
        elif fault == "cancelled":
            run = await value.guard._require_session().get(SourceSyncRun, value.admission.run_id)
            run.status = "cancelled"

    monkeypatch.setattr(port, "_record_success", interrupted)
    with pytest.raises(ConflictException):
        await port.acknowledge(lease, receipt)
    async with primary_authority():
        session = value.guard._require_session()
        item = await session.get(BulkItem, lease.item_id)
        job = await session.get(Job, lease.job_id)
        attempt = await session.scalar(select(SourceImportAttempt))
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        assert item.receipt_json is None and attempt.receipt_json is None
        assert await session.get(SourceImportedVersion, attempt.id) is None
        assert item.status == job.status == "running"
        assert job.worker_id == lease.worker_id and job.attempts == lease.attempt
        assert origin.state == "pending" and origin.published_native_version_id is None
        assert (await session.get(CatalogEntry, lease.source_id)).status == "pending"
        assert (await session.get(CatalogEntry, lease.asset_id)).status == "pending"


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize(
    "replace_remote", [False, True, "ack_rollback", "membership", "local_aba", "expired", "superseded",
                       "admission_resume", "initial_forensic", "membership_restored",
                       "receipt_substitution", "membership_restored_stale", "superseded_worker",
                       "superseded_attempt", "cancelled", "admission_resume_changed_bytes"]
)
async def test_source_document_native_pipeline_commits_a_real_receipt_and_recovers_acknowledgement(
    claimed_source_file,
    source_database,
    tmp_path,
    monkeypatch,
    replace_remote,
):
    from dataclasses import fields

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from flycanon.config import CanonSettings
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetService
    from flycanon.core.services.ingestion.chunker import ParagraphChunker
    from flycanon.core.services.ingestion.ingestion_service import IngestionService
    from flycanon.core.services.ingestion.loaders import default_registry
    from flycanon.core.services.metadata import MetadataExtractor
    from flycanon.core.services.retrieval.corpus_factory import CorpusContext
    from flycanon.core.services.retrieval.index_service import IndexService
    from flycanon.core.services.retrieval.pgvector_store import RlsPgVectorVectorStore
    from flycanon.core.services.retrieval.postgres_corpus import PostgresCorpus
    from flycanon.core.services.sources.intake_runtime import build_intake_components
    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.sources.lineage.pipeline import DocumentLineagePipeline
    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.data import TenantGucCustomizer
    from flycanon.models.entities.embedding_set import EmbeddingSetRow
    from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
    from flycanon.models.entities.source import SourceRow
    from flycanon.models.entities.workspace import Workspace
    from flycanon.models.repositories.chunk_repository import ChunkRepository
    from flycanon.models.repositories.embedding_set_repository import EmbeddingSetRepository
    from flycanon.models.repositories.source_repository import SourceRepository
    from pyfly.agentic.content.binary import BinaryNormalizer
    from pyfly.agentic.vectorstores import TenantScopedVectorStore
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import func, select
    from test_source_migration_postgres import load

    from koinon.knowledge.adapters import NativeDomains, native_scope
    from koinon.knowledge.bulk.native import NativeBulkIntake
    from koinon.knowledge.entities import DomainBinding

    current = claimed_source_file
    value, lease = current.producer, current.lease
    target, _, engine = source_database
    with engine.begin() as connection:
        for entity in (Workspace, SourceRow, EmbeddingSetRow, KnowledgeChunkRow):
            entity.__table__.create(connection)
        with Operations.context(MigrationContext.configure(connection)):
            for name in (
                "20261027_1600_0020_source_lineage.py",
                "20261031_1800_0021_pinned_originals.py",
                "20261110_2300_0023_source_publication_baselines.py",
            ):
                load("packages/canon/migrations/koinon_versions/" + name).upgrade()
    registry = value.review.context.get_bean(DataSourceRegistry)
    native = registry.register(
        "source_native", target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    )
    registry.add_customizer(TenantGucCustomizer(native.name), datasource=native.name)
    source_repository = SourceRepository(native.sessionmaker, engine=native.engine)
    lineage = DocumentLineage(source_repository, LocalFsObjectStore(str(tmp_path / "native-originals")))
    settings = CanonSettings(store_originals=True, pii_policy="disabled")
    corpus = CorpusContext(
        PostgresCorpus(datasource=native),
        TenantScopedVectorStore(RlsPgVectorVectorStore(datasource=native, dimension=64, create_schema=True)),
        "pgvector",
    )
    await corpus.initialise()
    calls = []

    class Embedder:
        model = "controlled:source-test"

        async def embed(self, texts):
            _no_remote_unit()
            calls.append(tuple(texts))
            return [[1.0] * 64 for _ in texts]

    class Embeddings:
        def for_binding(self, binding):
            assert binding.set_id == "source-set"
            return Embedder()

    class Audit:
        async def record(self, **kwargs):
            assert kwargs["tenant_id"] == lease.tenant_id

    components = build_intake_components(
        binary_normalizer=BinaryNormalizer(),
        ingestion=IngestionService(loaders=default_registry(), chunker=ParagraphChunker()),
        loaders=default_registry(),
        embeddings=Embedder(),
        indexer=IndexService(context=corpus),
        metadata_extractor=MetadataExtractor(),
        source_repository=source_repository,
        chunk_repository=ChunkRepository(native.sessionmaker, engine=native.engine),
        audit=Audit(),
        event_publisher=None,
        object_store=lineage.store,
        settings=settings,
        embedding_sets=EmbeddingSetService(
            repository=EmbeddingSetRepository(native.sessionmaker, engine=native.engine), settings=settings
        ),
        embedding_registry=Embeddings(),
    )
    pipeline = DocumentLineagePipeline(components, lineage)
    intake = IntakeService(
        **{
            field.name: getattr(components, field.name)
            for field in fields(components)
            if field.name != "policy"
        },
        lineage_pipeline=pipeline,
        intake_policy=components.policy,
    )
    with native_scope("canon", lease.tenant_id, "source-native-workspace", lease.subject):
        async with infrastructure_unit(native) as session:
            session.add(
                Workspace(
                    id="source-native-workspace",
                    tenant_id=lease.tenant_id,
                    name="Native source",
                    active_embedding_set_id="source-set",
                )
            )
            session.add(
                EmbeddingSetRow(
                    id="source-set",
                    tenant_id=lease.tenant_id,
                    workspace_id="source-native-workspace",
                    provider="controlled",
                    model="source-test",
                    dimensions=64,
                    status="active",
                    config_fingerprint="0" * 64,
                )
            )
    port, _ = await source_ack_port(current)
    # Exercise the real adapter and native pipeline with a deterministic local embedder;
    # provider credential/model selection is covered by its separate connection tests.
    domains = SimpleNamespace(_resolve=lambda kind: {IntakeService: intake, DocumentLineage: lineage}[kind])

    async def ingest_document(**kwargs):
        return await NativeDomains.ingest_document.__wrapped__(domains, **kwargs)

    domains.ingest_document = ingest_document
    port.facade().domains = domains
    del port.inspect_committed
    receipt = await port.execute(lease, b"source!")
    assert receipt.source_version_id and receipt.extraction_id and receipt.n_chunks == 1
    assert calls == [("source!",)]
    with native_scope("canon", lease.tenant_id, "source-native-workspace", lease.subject):
        async with infrastructure_unit(native) as session:
            assert await session.scalar(select(func.count()).select_from(KnowledgeChunkRow)) == 1
    # A new intake instance recovers the committed immutable receipt without parsing again.
    restarted = NativeBulkIntake(port.facades, current.files.records, current.queue)
    if replace_remote == "initial_forensic":
        await assert_revoked_native_receipt_is_private(current, restarted, receipt)
        assert calls == [("source!",)]
        return
    assert (await restarted.inspect_committed(lease)).receipt == receipt
    await restarted.acknowledge(lease, receipt)
    async with primary_authority():
        session = value.guard._require_session()
        assert (await session.get(Job, lease.job_id)).status == "succeeded"
        assert (
            await session.scalar(
                select(func.count())
                .select_from(DomainBinding)
                .where(DomainBinding.catalog_id.in_((lease.source_id, lease.asset_id)))
            )
            == 2
        )
    assert calls == [("source!",)]

    if not replace_remote:
        return

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.dtos import DownloadReceipt
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
    from koinon.integrations.content_sources.sync_entities import SourceMappingPolicy, SourceSyncState
    from koinon.integrations.content_sources.sync_replacement import SourceReplacements
    from koinon.knowledge.content import ContentUpdates

    mappings = value.review.context.get_bean(SourceMappings)
    async with primary_authority():
        session = value.guard._require_session()
        mapping = await session.get(SourceMapping, value.admission.mapping_id)
        policy = await session.get(SourceMappingPolicy, value.execution.policy_id)
    capture = await mappings.remote_capture(value.admission.owner, value.admission.tenant_id, mapping, policy)
    async with primary_authority(read_only=False):
        await value.writer.authority.source_destination(value.admission)
        session = value.guard._require_session()
        assert await SourceRunRepository(session=session).finish(value.execution, capture=capture)
        revision = (await session.get(SourceSyncState, mapping.id)).revision
    value.changed["version"] = "v2"
    catalog = value.writer.authority.catalog
    private_only = catalog.get
    monkeypatch.setattr(catalog, "get", CatalogService.get.__get__(catalog, CatalogService))
    try:
        started = await mappings.execute(
            value.admission.owner,
            value.admission.tenant_id,
            mapping.id,
            "sync",
            SourceControlInput(operation_id=str(uuid4()), expected_revision=revision),
        )
    finally:
        monkeypatch.setattr(catalog, "get", private_only)
    async with primary_authority(read_only=False):
        await value.writer.authority.source_destination(value.admission)
        session = value.guard._require_session()
        next_lease = await SourceRunRepository(session=session).claim(
            value.admission.tenant_id, value.admission.owner, started.run_id, "replacement-worker"
        )
        from koinon.integrations.content_sources.settings import ContentSourceSettings

        state = await session.get(SourceSyncState, mapping.id)
        maximum = value.review.context.get_bean(ContentSourceSettings).sync_max_scan_items
        state.scan_max_items, state.scan_observed_count = maximum, 0
        state.revision += 1
        await session.flush()
        assert state.scan_max_items == maximum and state.scan_observed_count == 0
        pins = await SourceCheckpoints(session=session).append(
            next_lease,
            0,
            WalkPage((WalkItem(replace(value.remote_item, version="v2"), ("selected",)),), None, True, 1),
            cursor_ciphertext=None,
        )
    next_admission = replace(value.admission, run_id=next_lease.run_id, items=pins)
    original = mappings.browser._source
    downloads = []

    @asynccontextmanager
    async def remote(scope, token):
        async with original(scope, token) as adapter:

            async def download(item, sink, *, max_bytes, export_mime):
                from hashlib import sha256

                _no_remote_unit()
                downloads.append(item.version)
                payload = (
                    b"changed" if replace_remote == "admission_resume_changed_bytes" and len(downloads) > 1
                    else b"source!"
                )
                await sink.write(payload)
                return DownloadReceipt(
                    scope, item.item_id, item.version, len(payload),
                    sha256(payload).hexdigest(), item.mime_type,
                )

            adapter.download = download
            yield adapter

    monkeypatch.setattr(mappings.browser, "_source", remote)

    @asynccontextmanager
    async def models(*args, **kwargs):
        _no_remote_unit()
        yield

    domains.model_connections = models
    domains._resolve = lambda kind: {
        IntakeService: intake,
        DocumentLineage: lineage,
        SourceRepository: source_repository,
    }[kind]

    async def replace_document(**kwargs):
        return await NativeDomains.replace_document(domains, **kwargs)

    domains.replace_document = replace_document
    replacement = SourceReplacements(
        value.writer,
        mappings,
        SimpleNamespace(get=lambda: ContentUpdates(port.facade())),
        SimpleNamespace(get=lambda: current.files),
    )
    if isinstance(replace_remote, str):
        if replace_remote in {"admission_resume", "admission_resume_changed_bytes"}:
            async def interrupt_reserved(*args, **kwargs):
                raise RuntimeError("reserved replacement interrupted")

            with monkeypatch.context() as interrupted_call:
                interrupted_call.setattr(domains, "replace_document", interrupt_reserved)
                with pytest.raises(RuntimeError, match="reserved replacement interrupted"):
                    await replacement.execute(next_admission, next_lease)
        else:
            complete = value.guard.committed_replacement

            async def lose_acknowledgement(*args, **kwargs):
                await complete(*args, **kwargs)
                raise RuntimeError("acknowledgement transaction interrupted")

            with monkeypatch.context() as interrupted_call:
                interrupted_call.setattr(value.guard, "committed_replacement", lose_acknowledgement)
                with pytest.raises(RuntimeError, match="acknowledgement transaction interrupted"):
                    await replacement.execute(next_admission, next_lease)
        async with primary_authority(read_only=False):
            session = value.guard._require_session()
            pending = await session.scalar(select(SourceImportAttempt).where(
                SourceImportAttempt.content_operation_id.is_not(None)
            ))
            interrupted = await session.get(SourcePublicationBaseline, pending.id)
            origin = await session.get(SourceObject, next_admission.items[0].object_id)
            assert interrupted.acknowledgement_json is None and pending.receipt_json is None
            assert origin.published_native_version_id == receipt.source_version_id
            primary_engine = session.get_bind()
            if replace_remote in {"membership", "membership_restored", "membership_restored_stale"}:
                await session.execute(update(Membership).where(
                    Membership.id == value.admission.owner
                ).values(role="viewer"))
            elif replace_remote == "local_aba":
                row = await session.get(CatalogEntry, pending.source_id)
                original_name = row.name
                await session.execute(update(CatalogEntry).where(
                    CatalogEntry.id == row.id
                ).values(name="Local edit"))
                await session.execute(update(CatalogEntry).where(
                    CatalogEntry.id == row.id
                ).values(name=original_name))
            elif replace_remote == "expired":
                await session.execute(update(Job).where(Job.id == next_lease.job_id).values(
                    lease_until=datetime(2000, 1, 1, tzinfo=UTC)
                ))
            elif replace_remote == "superseded":
                await session.execute(update(Job).where(Job.id == next_lease.job_id).values(
                    worker_id="successor", attempts=next_lease.attempt + 1
                ))
            elif replace_remote == "superseded_worker":
                await session.execute(update(Job).where(Job.id == next_lease.job_id).values(
                    worker_id="successor"
                ))
            elif replace_remote == "superseded_attempt":
                await session.execute(update(Job).where(Job.id == next_lease.job_id).values(
                    attempts=next_lease.attempt + 1
                ))
        if replace_remote == "admission_resume_changed_bytes":
            with pytest.raises(ConflictException):
                await replacement.execute(next_admission, next_lease)
            async with primary_authority():
                session = value.guard._require_session()
                assert (await session.get(SourceImportAttempt, pending.id)).receipt_json is None
                assert (await session.get(SourcePublicationBaseline, pending.id)).acknowledgement_json is None
                assert await session.scalar(select(func.count()).select_from(SourceImportAttempt).where(
                    SourceImportAttempt.content_operation_id.is_not(None)
                )) == 1
            assert downloads == ["v2", "v2"] and calls == [("source!",)]
            return
        if replace_remote == "cancelled":
            async with primary_authority():
                revision = (await value.guard._require_session().get(SourceSyncState, mapping.id)).revision
            with monkeypatch.context() as cancellation:
                cancellation.setattr(catalog, "get", CatalogService.get.__get__(catalog, CatalogService))
                await mappings.execute(
                    lease.subject, lease.tenant_id, mapping.id, "cancel",
                    SourceControlInput(operation_id=str(uuid4()), expected_revision=revision),
                    target_run_id=next_lease.run_id,
                )
        if replace_remote in {"superseded", "superseded_worker", "superseded_attempt"}:
            with pytest.raises(ConflictException):
                await replacement.execute(next_admission, next_lease)
            async with primary_authority():
                session = value.guard._require_session()
                assert (await session.get(SourceImportAttempt, pending.id)).receipt_json is None
                assert (await session.get(SourcePublicationBaseline, pending.id)).acknowledgement_json is None
            assert downloads == ["v2"] and calls == [("source!",), ("source!",)]
            return
        if replace_remote in {
            "membership", "membership_restored", "membership_restored_stale", "local_aba", "expired",
            "cancelled",
        }:
            from sqlalchemy import event

            from koinon.catalog.entities import AuditEvent

            statements = []

            def capture_statement(connection, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT"):
                    statements.append(statement)

            calls_before = (len(downloads), len(calls), len(value.review.state.calls))
            event.listen(primary_engine, "before_cursor_execute", capture_statement)
            try:
                outcome = await replacement.execute(next_admission, next_lease)
                assert outcome.outcome == "conflict"
                assert await replacement.execute(next_admission, next_lease) == outcome
            finally:
                event.remove(primary_engine, "before_cursor_execute", capture_statement)
            assert (len(downloads), len(calls)) == calls_before[:2]
            if replace_remote in {"membership", "membership_restored", "membership_restored_stale"}:
                assert len(value.review.state.calls) == calls_before[2]
                assert statements and all(
                    field not in statement for statement in statements for field in (
                        "lattice_catalog.name", "koinon_content_connections.secret_ciphertext",
                        "koinon_content_sync_observations.event_json", "koinon_content_policies.policy_json",
                    )
                )
            async with primary_authority():
                session = value.guard._require_session()
                retained = await session.get(SourceImportAttempt, pending.id)
                baseline = await session.get(SourcePublicationBaseline, pending.id)
                origin = await session.get(SourceObject, next_admission.items[0].object_id)
                assert retained.receipt_json["source_attempt_id"] == pending.id
                assert baseline.acknowledgement_json is None
                assert origin.published_native_version_id == receipt.source_version_id
                assert await session.scalar(select(func.count()).select_from(AuditEvent).where(
                    AuditEvent.action == "knowledge.source.receipt_recorded",
                    AuditEvent.resource_id == outcome.operation_id,
                )) == 1
            if replace_remote not in {"membership_restored", "membership_restored_stale"}:
                return
            async with primary_authority(read_only=False):
                session = value.guard._require_session()
                await session.execute(update(Membership).where(
                    Membership.id == value.admission.owner
                ).values(role="admin"))
                if replace_remote == "membership_restored_stale":
                    previous_name = (await session.get(CatalogEntry, pending.asset_id)).name
                    await session.execute(update(CatalogEntry).where(
                        CatalogEntry.id == pending.asset_id
                    ).values(name="Local edit after receipt"))
                    await session.execute(update(CatalogEntry).where(
                        CatalogEntry.id == pending.asset_id
                    ).values(name=previous_name))
            if replace_remote == "membership_restored_stale":
                assert await replacement.execute(next_admission, next_lease) == outcome
                assert downloads == ["v2"] and calls == [("source!",), ("source!",)]
                return
            from koinon.integrations.content_sources.sync_runs import (
                SourceReplacementAcknowledgementExecution,
            )
            from koinon.knowledge.bulk.ports import NativeCommit

            encoded = dict(retained.receipt_json)
            encoded.pop("operation_id")
            encoded["tables"] = ()
            ack_only = SourceReplacementAcknowledgementExecution(
                next_lease, pending.id, pending.content_operation_id, NativeCommit(**encoded)
            )
            with pytest.raises(ConflictException):
                await replacement.execute(next_admission, ack_only)
            with pytest.raises(ConflictException):
                async with replacement.publication(next_admission, ack_only):
                    pytest.fail("An acknowledgement cannot grant native publication")
            with pytest.raises(ConflictException):
                async with value.writer.structured_producer(
                    next_admission, execution=ack_only, operation=None, publication=None
                ):
                    pytest.fail("An acknowledgement cannot create a native dataset producer")
            with pytest.raises(ConflictException):
                async with replacement._publication(next_admission, replace(
                    ack_only, receipt=replace(ack_only.receipt, source_version_id=receipt.source_version_id)
                )):
                    pytest.fail("An altered receipt cannot enter acknowledgement publication")
    outcome = await replacement.execute(next_admission, next_lease)
    assert outcome.outcome == "acknowledged" and outcome.operation_id and outcome.attempt_id
    expected_downloads = ["v2", "v2"] if replace_remote == "admission_resume" else ["v2"]
    assert downloads == expected_downloads and calls == [("source!",), ("source!",)]
    if isinstance(replace_remote, str):
        assert outcome.attempt_id == pending.id
    async with primary_authority():
        session = value.guard._require_session()
        attempt = await session.get(SourceImportAttempt, outcome.attempt_id)
        baseline = await session.get(SourcePublicationBaseline, attempt.id)
        origin = await session.get(SourceObject, next_admission.items[0].object_id)
        assert attempt.content_operation_id == outcome.operation_id and attempt.intake_item_id is None
        assert attempt.remote_version == "v2" and attempt.sha256 == receipt.sha256
        assert attempt.receipt_json["source_version_id"] != receipt.source_version_id
        assert attempt.receipt_json["extraction_id"] != receipt.extraction_id
        assert baseline.previous_attempt_id == receipt.source_attempt_id
        assert attempt.receipt_json == {
            **baseline.acknowledgement_json["native_receipt"],
            "operation_id": outcome.operation_id,
        }
        assert origin.published_local_revision == "cpv1:" + baseline.acknowledgement_sha256
        assert origin.published_native_version_id == attempt.receipt_json["source_version_id"]
    replay = await replacement.execute(next_admission, next_lease)
    assert replay == outcome
    assert downloads == expected_downloads and calls == [("source!",), ("source!",)]

    if replace_remote == "receipt_substitution":
        from koinon.integrations.content_sources.replacement_receipts import ReplacementReceipts

        async with primary_authority(read_only=False):
            retained = await ReplacementReceipts(value.guard._require_session()).capture(
                next_admission, next_lease
            )
        observed = await replacement._inspect_document(
            next_admission, retained, None, ContentUpdates(port.facade()), retained=retained
        )
        assert observed.status == "committed" and retained.acknowledged
        for altered in (
            replace(observed.receipt, source_version_id=receipt.source_version_id),
            replace(observed.receipt, extraction_id=receipt.extraction_id),
        ):
            with pytest.raises(ConflictException):
                async with primary_authority(read_only=False):
                    await ReplacementReceipts(value.guard._require_session()).record(
                        next_admission, next_lease, retained, altered,
                        audit=value.writer.authority.catalog._audit,
                    )
        for altered in (
            replace(retained, content_operation_id="upload:" + lease.source_id),
            replace(retained, id=receipt.source_attempt_id),
            replace(retained, descriptor_sha256="0" * 64),
        ):
            with pytest.raises(ConflictException):
                await replacement._inspect_document(
                    next_admission, altered, None, ContentUpdates(port.facade()), retained=altered
                )
        assert await replacement.execute(next_admission, next_lease) == outcome
        assert downloads == expected_downloads and calls == [("source!",), ("source!",)]
        return

    from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
    from koinon.integrations.content_sources.mapping_preview import SourceMappingPreview

    selected = MappingReviewInput.model_validate(policy.policy_json["request"])
    preview = SourceMappingPreview(mappings.authority, mappings.connections, mappings.browser)

    async def local_collision():
        entries = [{
            "item_id": value.remote_item.item_id, "kind": "file", "reason": None,
            "filename": lease.filename, "relative_path": [lease.filename],
            "ancestry": [selected.root_id], "collision": "none",
        }]
        async with primary_authority(read_only=False):
            await preview.local_conflicts(
                value.admission.owner, value.admission.tenant_id, selected, entries, mapping_id=mapping.id
            )
        return entries[0]["collision"]

    monkeypatch.setattr(catalog, "get", CatalogService.get.__get__(catalog, CatalogService))
    assert await local_collision() == "none"
    await catalog.update(value.admission.owner, value.admission.tenant_id, attempt.source_id,
                         {"description": "Local change"})
    await catalog.update(value.admission.owner, value.admission.tenant_id, attempt.source_id,
                         {"description": ""})
    assert await local_collision() == "local_edit"


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["dataset"], indirect=True)
async def test_source_dataset_table_reservation_and_acknowledgement_use_exact_private_targets(
    claimed_source_file,
):
    from unittest.mock import AsyncMock

    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
    from koinon.knowledge.bulk.entities import BulkItem, BulkTableReservation
    from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation, NativeTableCommit
    from koinon.knowledge.bulk.structured_dtos import StructuredTablePlan

    current = claimed_source_file
    lease, value = current.lease, current.producer
    plan = StructuredTablePlan(
        ordinal=0,
        table_id=uuid4(),
        snapshot_id=uuid4(),
        name="Facts",
        member_key="root",
        parser_fingerprint="koinon.source-member-locators.v1",
    )
    plans = await current.queue.reserve_tables(lease, (plan,))
    assert await current.queue.reserve_tables(lease, (plan,)) == plans
    async with primary_authority():
        session = value.guard._require_session()
        item = await session.get(BulkItem, lease.item_id)
        reservation = DatasetReservation.stored(item.reservation_json)
        tables = list(
            await session.scalars(select(BulkTableReservation).where(BulkTableReservation.item_id == item.id))
        )
        assert len(tables) == 1 and tables[0].catalog_table_id == plans[0].catalog_table_id
        assert (await session.get(CatalogEntry, tables[0].catalog_table_id)).status == "pending"
    port, template = await source_ack_port(current, members=plans)
    receipt = NativeCommit(
        "structured",
        current.native_workspace,
        str(reservation.native_dataset_id),
        str(reservation.native_dataset_id),
        lease.sha256,
        lease.size_bytes,
        file_version_id=reservation.catalog_file_version_id,
        native_file_id=str(reservation.native_file_id),
        source_attempt_id=template.source_attempt_id,
        source_publication_sha256=template.source_publication_sha256,
        tables=(
            NativeTableCommit(plans[0].catalog_table_id, str(plan.table_id), str(plan.snapshot_id), 1, 2),
        ),
    )

    async def committed(_):
        _no_remote_unit()
        return NativeObservation("committed", receipt)

    port.inspect_committed = AsyncMock(side_effect=committed)
    await port.acknowledge(lease, receipt)
    async with primary_authority():
        session = value.guard._require_session()
        assert (await session.get(Job, lease.job_id)).status == "succeeded"
        for identifier in (
            lease.source_id,
            lease.asset_id,
            reservation.catalog_file_version_id,
            plans[0].catalog_table_id,
        ):
            assert (await session.get(CatalogEntry, identifier)).status == "ready"
    port.facade().catalog.get.assert_not_called()


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_source_acknowledgement_waits_for_canonical_targets_before_locking_the_job(
    claimed_source_file,
    source_database,
    monkeypatch,
):
    import asyncio
    import contextvars

    import psycopg
    from sqlalchemy import text

    current = claimed_source_file
    value, lease = current.producer, current.lease
    port, receipt = await source_ack_port(current)
    target, _, _ = source_database
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    waiting_pid = asyncio.get_running_loop().create_future()
    original = value.writer._execution
    checks = 0

    async def execution(*args, **kwargs):
        nonlocal checks
        result = await original(*args, **kwargs)
        if not kwargs["lock_job"]:
            checks += 1
            if checks == 2:
                waiting_pid.set_result(
                    await value.guard._require_session().scalar(text("SELECT pg_backend_pid()"))
                )
        return result

    monkeypatch.setattr(value.writer, "_execution", execution)
    task = None
    try:
        with psycopg.connect(uri) as owner:
            owner.execute("SELECT id FROM lattice_catalog WHERE id=%s FOR UPDATE", (lease.asset_id,))
            task = asyncio.create_task(port.acknowledge(lease, receipt), context=contextvars.Context())
            pid = await asyncio.wait_for(waiting_pid, 3)

            async def blocked():
                def state():
                    with psycopg.connect(uri) as observer:
                        return observer.execute(
                            "SELECT wait_event_type FROM pg_stat_activity WHERE pid=%s", (pid,)
                        ).fetchone()[0]

                while await asyncio.to_thread(state) != "Lock":
                    assert not task.done()
                    await asyncio.sleep(0.01)

            await asyncio.wait_for(blocked(), 3)
            # With inverted order, the waiter already owns this row and NOWAIT fails.
            assert (
                owner.execute(
                    "SELECT id FROM lattice_jobs WHERE id=%s FOR UPDATE NOWAIT", (lease.job_id,)
                ).fetchone()[0]
                == lease.job_id
            )
            owner.commit()
        await asyncio.wait_for(task, 5)
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_source_file_history_requires_matching_native_and_canonical_publication(
    claimed_source_file, monkeypatch
):
    from koinon.catalog.service import CatalogService
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.mapping_service import SourceMappings

    current = claimed_source_file
    value = current.producer
    service = value.review.context.get_bean(SourceMappings)
    catalog = value.writer.authority.catalog
    original = CatalogService.get.__get__(catalog, CatalogService)
    private_only = catalog.get
    monkeypatch.setattr(catalog, "get", original)
    page = await service.run_items("issuer|alice", "tenant", value.admission.run_id)
    assert len(page.items) == 1 and page.items[0].status == "processing"
    assert page.items[0].asset_id == current.lease.asset_id
    monkeypatch.setattr(catalog, "get", private_only)
    port, receipt = await source_ack_port(current)
    await port.acknowledge(current.lease, receipt)
    private_only.assert_not_called()
    monkeypatch.setattr(catalog, "get", original)
    page = await service.run_items("issuer|alice", "tenant", value.admission.run_id)
    assert len(page.items) == 1 and page.items[0].status == "searchable"
    async with primary_authority(read_only=False):
        origin = await value.guard._require_session().get(SourceObject, page.items[0].object_id)
        origin.published_native_version_id = "another-native-version"
    page = await service.run_items("issuer|alice", "tenant", value.admission.run_id)
    assert page.items[0].status == "indeterminate"


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["folder"], indirect=True)
@pytest.mark.parametrize("existing_name", ["finance", " FINANCE "])
async def test_source_folder_publication_rejects_current_normalized_sibling_collision(
    producer, existing_name
):
    from sqlalchemy import func, select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.sync_folders import SourceFolders

    value = producer
    await value.writer.authority.catalog.create(
        "issuer|alice",
        "tenant",
        kind="collection",
        name=existing_name,
        parent_id=value.admission.destination[2],
    )
    with pytest.raises(ConflictException):
        await SourceFolders(value.writer).publish(value.admission, value.execution)
    async with primary_authority():
        session = value.guard._require_session()
        assert (
            await session.scalar(
                select(func.count())
                .select_from(CatalogEntry)
                .where(CatalogEntry.parent_id == value.admission.destination[2])
            )
            == 1
        )
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        assert origin.published_local_revision is None


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("local_edit", [False, True])
async def test_source_descriptor_freezes_original_pins_before_native_creation(
    claimed_source_file, local_edit
):
    from sqlalchemy import select, update

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline

    current = claimed_source_file
    writer = current.producer.writer
    if local_edit:
        async with primary_authority(read_only=False):
            session = current.producer.guard._require_session()
            row = await session.get(CatalogEntry, current.lease.source_id)
            original = row.name
            await session.execute(
                update(CatalogEntry).where(CatalogEntry.id == row.id).values(name="Local edit")
            )
            await session.execute(update(CatalogEntry).where(CatalogEntry.id == row.id).values(name=original))
        with pytest.raises(ConflictException):
            async with current.queue.publication(current.lease) as admission:
                await writer.freeze_publication(admission, execution=current.lease)
        async with primary_authority():
            assert (
                await current.producer.guard._require_session().scalar(select(SourcePublicationBaseline))
            ).descriptor_json is None
        return
    async with current.queue.publication(current.lease) as admission:
        binding = await writer.freeze_publication(admission, execution=current.lease)
    async with current.queue.publication(current.lease) as admission:
        assert await writer.freeze_publication(admission, execution=current.lease) == binding
    async with primary_authority():
        baseline = await current.producer.guard._require_session().scalar(select(SourcePublicationBaseline))
        assert (
            baseline.descriptor_sha256 == binding.descriptor_sha256 and len(binding.descriptor_sha256) == 64
        )
        assert baseline.attempt_id == binding.attempt_id
        assert baseline.descriptor_json["native"]["operation_id"] == "upload:" + current.lease.source_id
        assert baseline.descriptor_json["members"] == []
        assert [value["pin"]["catalog_id"] for value in baseline.descriptor_json["targets"]] == sorted(
            [current.lease.source_id, current.lease.asset_id]
        )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["dataset"], indirect=True)
async def test_source_dataset_pins_each_table_once_with_its_primary_reservation(claimed_source_file):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.publication_entities import SourcePublicationTarget
    from koinon.knowledge.bulk.structured_dtos import StructuredTablePlan

    current = claimed_source_file
    plan = StructuredTablePlan(
        ordinal=0,
        table_id=uuid4(),
        snapshot_id=uuid4(),
        name="Facts",
        member_key="root",
        parser_fingerprint="koinon.source-member-locators.v1",
    )
    planned = await current.queue.reserve_tables(current.lease, (plan,))
    assert await current.queue.reserve_tables(current.lease, (plan,)) == planned
    async with primary_authority():
        session = current.producer.guard._require_session()
        pins = list((await session.scalars(select(SourcePublicationTarget))).all())
        assert len(pins) == 4
        member = next(pin for pin in pins if pin.role == "member")
        assert member.catalog_id == planned[0].catalog_table_id and member.disposition == "add"
        row = await session.get(CatalogEntry, member.catalog_id)
        assert (
            member.mutation_revision == row.mutation_revision and member.parent_id == current.lease.asset_id
        )


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_source_intake_retains_canonical_revisions_in_the_reservation_transaction(claimed_source_file):
    from sqlalchemy import select

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.publication_entities import (
        SourcePublicationBaseline,
        SourcePublicationTarget,
    )

    current = claimed_source_file
    async with primary_authority():
        session = current.producer.guard._require_session()
        baseline = await session.scalar(select(SourcePublicationBaseline))
        assert baseline is not None
        assert (baseline.source_id, baseline.asset_id, baseline.producer_kind) == (
            current.lease.source_id,
            current.lease.asset_id,
            "initial_document",
        )
        assert baseline.descriptor_json is None and baseline.acknowledgement_json is None
        pins = list(
            (
                await session.scalars(
                    select(SourcePublicationTarget).order_by(SourcePublicationTarget.catalog_id)
                )
            ).all()
        )
        assert {pin.catalog_id for pin in pins} == {current.lease.source_id, current.lease.asset_id}
        for pin in pins:
            row = await session.get(CatalogEntry, pin.catalog_id)
            assert pin.attempt_id == baseline.attempt_id and pin.disposition == "add"
            assert pin.mutation_revision == row.mutation_revision and pin.status == row.status == "pending"
            assert pin.parent_id == row.parent_id and pin.native_id is None


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_source_acknowledgement_cannot_bless_canonical_aba_after_native_commit(claimed_source_file):
    from sqlalchemy import select, update

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceObject

    current = claimed_source_file
    value = current.producer
    port, receipt = await source_ack_port(current)
    async with primary_authority(read_only=False):
        session = value.guard._require_session()
        source = await session.get(CatalogEntry, current.lease.source_id)
        original_name = source.name
        await session.execute(
            update(CatalogEntry).where(CatalogEntry.id == source.id).values(name="Local edit")
        )
        await session.execute(
            update(CatalogEntry).where(CatalogEntry.id == source.id).values(name=original_name)
        )
    with pytest.raises(ConflictException):
        await port.acknowledge(current.lease, receipt)
    assert (await port.inspect_committed(current.lease)).receipt == receipt
    async with primary_authority():
        session = value.guard._require_session()
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        assert origin.published_native_version_id is None and origin.published_local_revision is None
        assert (await session.scalar(select(SourceImportAttempt))).receipt_json is None
        assert (await session.get(Job, current.lease.job_id)).status == "running"


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_source_native_fence_rejects_local_aba_before_entering_native_work(claimed_source_file):
    from sqlalchemy import update

    from koinon.catalog.entities import CatalogEntry

    current = claimed_source_file
    await source_ack_port(current)
    async with primary_authority(read_only=False):
        session = current.producer.guard._require_session()
        row = await session.get(CatalogEntry, current.lease.asset_id)
        original_name = row.name
        await session.execute(update(CatalogEntry).where(CatalogEntry.id == row.id).values(name="Edited"))
        await session.execute(
            update(CatalogEntry).where(CatalogEntry.id == row.id).values(name=original_name)
        )
    entered = False
    with pytest.raises(ConflictException):
        async with current.queue.publication(current.lease):
            entered = True
    assert not entered


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_forensic_receipt_does_not_create_published_source_authority(claimed_source_file):
    from sqlalchemy import func, select

    from koinon.integrations.content_sources.import_entities import SourceImportAttempt
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
    from koinon.integrations.content_sources.sync_entities import SourceImportedVersion, SourceSyncWork

    current = claimed_source_file
    port, receipt = await source_ack_port(current)
    async with primary_authority(read_only=False):
        await current.producer.guard._require_session().execute(
            update(Membership).where(Membership.id == current.lease.subject).values(role="viewer")
        )
    await port.settle_source_receipt(current.lease, receipt)
    await port.settle_source_receipt(current.lease, receipt)
    async with primary_authority():
        session = current.producer.guard._require_session()
        assert await session.scalar(select(func.count()).select_from(SourceImportedVersion)) == 0
        baseline = await session.get(SourcePublicationBaseline, receipt.source_attempt_id)
        attempt = await session.get(SourceImportAttempt, receipt.source_attempt_id)
        origin = await session.get(SourceObject, current.producer.admission.items[0].object_id)
        assert attempt.receipt_json["source_publication_sha256"] == baseline.descriptor_sha256
        assert baseline.acknowledgement_json is None and origin.published_native_version_id is None
        work = await session.get(SourceSyncWork, current.producer.admission.items[0].work_id)
        assert (work.status, work.error_code) == ("conflict", "SOURCE_PUBLICATION_NOT_ACKNOWLEDGED")


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
async def test_acknowledgement_replay_returns_retained_outcome_without_rebasing_local_edits(
    claimed_source_file,
):
    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline

    current = claimed_source_file
    port, receipt = await source_ack_port(current)
    await port.acknowledge(current.lease, receipt)
    async with primary_authority(read_only=False):
        session = current.producer.guard._require_session()
        baseline = await session.get(SourcePublicationBaseline, receipt.source_attempt_id)
        retained = baseline.acknowledgement_json
        await session.execute(
            update(CatalogEntry).where(CatalogEntry.id == current.lease.asset_id).values(name="Local name")
        )
    calls = len(current.producer.review.state.calls)
    port.inspect_committed.reset_mock()
    await port.acknowledge(current.lease, receipt)
    port.inspect_committed.assert_not_awaited()
    assert len(current.producer.review.state.calls) == calls
    with pytest.raises(ConflictException):
        await port.acknowledge(current.lease, replace(receipt, native_asset_id="foreign"))
    port.inspect_committed.assert_not_awaited()
    await port.settle_source_receipt(current.lease, receipt)
    async with primary_authority():
        session = current.producer.guard._require_session()
        assert (await session.get(CatalogEntry, current.lease.asset_id)).name == "Local name"
        assert (
            await session.get(SourcePublicationBaseline, receipt.source_attempt_id)
        ).acknowledgement_json == retained
    async with primary_authority(read_only=False):
        await current.producer.guard._require_session().execute(
            update(Membership).where(Membership.id == current.lease.subject).values(role="viewer")
        )
    with pytest.raises(AccessDenied):
        await port.acknowledge(current.lease, receipt)


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["dataset"], indirect=True)
async def test_structured_source_producer_is_bound_to_exact_task_and_lifetime(claimed_source_file):
    import asyncio

    from pyfly.data.relational.datasource_registry import DataSourceRegistry

    from koinon.knowledge.bulk.dataset_native import DatasetBulkNative
    from koinon.knowledge.lineage.service import NativeStructuredLineage

    current = claimed_source_file
    writer = current.producer.writer
    writer.lineage = SimpleNamespace(
        get=lambda: NativeStructuredLineage(current.producer.review.context.get_bean(DataSourceRegistry))
    )
    adapter = DatasetBulkNative(None, None, current.files.records, current.queue, None)
    identity = await adapter.identity(current.lease)
    admission = await writer.admission_for(current.lease)
    async with writer.structured_producer(
        admission,
        execution=current.lease,
        operation=identity,
        publication=lambda: current.queue.publication(current.lease),
    ) as producer:
        assert producer.attempt_id
        with pytest.raises(ConflictException):
            await asyncio.create_task(producer.before_model(()))
    with pytest.raises(ConflictException):
        await producer.before_model(())


@pytest.mark.integration
@pytest.mark.parametrize("lifecycle", ["postgres"], indirect=True)
@pytest.mark.parametrize("producer", ["dataset"], indirect=True)
@pytest.mark.parametrize(
    "scenario",
    ["complete", "prepared_resume", "revoked", "local_aba", "replacement_admission",
     "replacement_execution", "replacement_ack_rollback", "replacement_membership", "replacement_aba",
     "replacement_prepared_resume", "replacement_admission_resume", "parser_upsert", "initial_forensic",
     "replacement_membership_restored", "replacement_native_admitted",
     "replacement_native_admitted_blob", "replacement_native_admitted_unknown_head",
     "replacement_native_admitted_file", "replacement_native_admitted_artifact",
     "replacement_native_admitted_snapshot"],
)
async def test_source_dataset_runs_real_native_stages_and_recovers_its_exact_receipt(
    claimed_source_file,
    source_database,
    tmp_path,
    monkeypatch,
    scenario,
):
    from uuid import UUID

    from alembic import command
    from flyquery.config import FlyquerySettings
    from flyquery.core.eda.ingest_publisher import IngestPublisher
    from flyquery.core.services.ingestion.lineage import LineageDenied
    from flyquery.core.services.ingestion.stages import embed
    from flyquery.core.services.storage.adapters.local_fs import LocalFsObjectStore
    from flyquery.core.services.workspaces.workspace_repository import WorkspaceRepository
    from flyquery.core.services.workspaces.workspace_service import WorkspaceService
    from flyquery.data import TenantGucCustomizer
    from flyquery.models.entities.schema import SchemaObject, SchemaSnapshot
    from flyquery.models.entities.workspace import Workspace
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import func, select
    from test_source_migration_postgres import ROOT, load

    from koinon.catalog.entities import CatalogEntry
    from koinon.integrations.content_sources.mapping_entities import SourceObject
    from koinon.integrations.content_sources.publication_entities import SourcePublicationBaseline
    from koinon.knowledge.adapters import native_scope
    from koinon.knowledge.bulk.dataset_native import DatasetBulkNative
    from koinon.knowledge.bulk.native import NativeBulkIntake
    from koinon.knowledge.bulk.structured_pipeline import StructuredBulkPipeline
    from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository
    from koinon.knowledge.lineage.service import NativeStructuredLineage

    current = claimed_source_file
    value, lease = current.producer, current.lease
    target, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "structured",
            ROOT / "packages/structured/migrations/versions",
            connection,
        )
        command.upgrade(config, "head")
        connection.commit()
    registry = value.review.context.get_bean(DataSourceRegistry)
    native = registry.register(
        "structured", target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    )
    registry.add_customizer(TenantGucCustomizer(native.name), datasource=native.name)
    settings = FlyquerySettings(pii_scanner="disabled")
    settings.bind_native_resources(None, registry)
    repository = StructuredBulkRepository(SimpleNamespace(get=lambda: settings))
    pipeline = StructuredBulkPipeline(
        repository,
        current.queue,
        SimpleNamespace(get=lambda: LocalFsObjectStore(str(tmp_path / "structured-originals"))),
        SimpleNamespace(get=lambda: WorkspaceService(WorkspaceRepository(native.sessionmaker))),
        SimpleNamespace(get=lambda: IngestPublisher(None)),
    )
    value.writer.lineage = SimpleNamespace(get=lambda: NativeStructuredLineage(registry))
    calls = []

    class Embedder:
        model = "controlled:source-test"

        async def embed_batch(self, texts):
            _no_remote_unit()
            calls.append(tuple(texts))
            if scenario in {"revoked", "local_aba"}:
                async with primary_authority(read_only=False):
                    session = value.guard._require_session()
                    if scenario == "revoked":
                        await session.execute(
                            update(Membership).where(Membership.id == lease.subject).values(role="viewer")
                        )
                    else:
                        original = (await session.get(CatalogEntry, lease.asset_id)).name
                        await session.execute(
                            update(CatalogEntry)
                            .where(CatalogEntry.id == lease.asset_id)
                            .values(name="Edited")
                        )
                        await session.execute(
                            update(CatalogEntry)
                            .where(CatalogEntry.id == lease.asset_id)
                            .values(name=original)
                        )
            return [[1.0] * 1536 for _ in texts]

    monkeypatch.setattr(embed, "build_embedder", lambda settings: Embedder())

    @asynccontextmanager
    async def connections(*args, **kwargs):
        _no_remote_unit()
        assert kwargs["roles"] == ("structured.embedding",)
        with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
            yield

    port, _ = await source_ack_port(current)
    dataset = DatasetBulkNative(repository, pipeline, current.files.records, current.queue, port.facades)
    port.facade().domains = SimpleNamespace(
        _resolve=lambda kind: {DatasetBulkNative: dataset}[kind],
        model_connections=connections,
    )
    del port.inspect_committed
    with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
        async with infrastructure_unit(native) as session:
            session.add(
                Workspace(
                    id=UUID(current.native_workspace), tenant_id=lease.tenant_id, slug="source", name="Source"
                )
            )
    if scenario in {"revoked", "local_aba"}:
        with pytest.raises((ConflictException, AccessDenied, LineageDenied)):
            await port.execute(lease, current.content)
        with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
            async with infrastructure_unit(native) as session:
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(SchemaSnapshot)
                        .where(SchemaSnapshot.status == "READY")
                    )
                    == 0
                )
                assert (
                    await session.scalar(
                        select(func.count())
                        .select_from(SchemaObject)
                        .where(SchemaObject.embedding.is_not(None))
                    )
                    == 0
                )
        async with primary_authority():
            baseline = await value.guard._require_session().scalar(select(SourcePublicationBaseline))
            assert baseline.descriptor_sha256 and baseline.acknowledgement_json is None
        assert len(calls) == 1
        return
    if scenario == "prepared_resume":
        identity = await dataset.identity(lease)
        async with (
            connections(roles=("structured.embedding",)),
            dataset.producer(lease, identity) as producer,
        ):
            prepared = await pipeline.prepare(lease, identity, current.content, _source_producer=producer)
            assert prepared.status == "prepared" and prepared.source_publication_sha256

        async def forbidden_processing(*args, **kwargs):
            pytest.fail("A prepared operation must not replay parsing or model work")

        monkeypatch.setattr(pipeline, "prepare", forbidden_processing)
        receipt = await DatasetBulkNative(
            repository, pipeline, current.files.records, current.queue, port.facades
        ).finalize_prepared(lease)
    else:
        receipt = await port.execute(lease, current.content)
    assert receipt.domain == "structured" and receipt.source_attempt_id
    assert receipt.source_publication_sha256 and len(receipt.tables) == 1
    assert receipt.tables[0].n_rows_actual == 2 and receipt.tables[0].n_columns == 1
    assert len(calls) == 1
    if scenario == "parser_upsert":
        from flyquery.core.services.ingestion.stages.parse import _insert_table
        from flyquery.models.entities.dataset import Dataset
        from flyquery.models.entities.file import File
        from flyquery.models.entities.table import Table

        ordinary_dataset, first_file, next_file, first_table, next_table = (uuid4() for _ in range(5))
        with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
            async with infrastructure_unit(native) as session:
                previous_dataset = await session.get(Dataset, UUID(receipt.native_asset_id))
                previous_file = await session.get(File, UUID(receipt.native_file_id))
                session.add(
                    Dataset(
                        **{
                            **{
                                column.name: getattr(previous_dataset, column.name)
                                for column in Dataset.__table__.columns
                            },
                            "id": ordinary_dataset,
                            "name": "Ordinary local dataset",
                            "metadata_json": {},
                        }
                    )
                )
                await session.flush()
                for identifier in (first_file, next_file):
                    session.add(
                        File(
                            **{
                                **{
                                    column.name: getattr(previous_file, column.name)
                                    for column in File.__table__.columns
                                },
                                "id": identifier,
                                "dataset_id": ordinary_dataset,
                            }
                        )
                    )
            values = dict(
                tenant_id=lease.tenant_id,
                workspace_id=UUID(current.native_workspace),
                dataset_id=ordinary_dataset,
                name="ordinary",
                qualified_name="ordinary.table",
                sheet_or_json_path=None,
                session_factory=native.sessionmaker,
            )
            assert (
                await _insert_table(table_id=first_table, source_file_id=first_file, **values) == first_table
            )
            assert await _insert_table(table_id=uuid4(), source_file_id=next_file, **values) == first_table
            with pytest.raises(ConflictException):
                await _insert_table(table_id=uuid4(), source_file_id=first_file, append_only=True, **values)
            async with infrastructure_unit(native) as session:
                retained_table = await session.get(Table, first_table)
                assert retained_table.source_file_id == next_file
                retained_table.is_active, retained_table.archived_at = False, datetime.now(UTC)
            assert (
                await _insert_table(
                    table_id=next_table, source_file_id=first_file, append_only=True, **values
                )
                == next_table
            )
            assert await _insert_table(table_id=uuid4(), source_file_id=next_file, **values) == next_table
            async with infrastructure_unit(native) as session:
                historical = await session.get(Table, first_table)
                active = await session.get(Table, next_table)
                assert historical.name == active.name == "ordinary"
                assert not historical.is_active and historical.archived_at is not None
                assert active.is_active and active.source_file_id == next_file
    restarted = NativeBulkIntake(port.facades, current.files.records, current.queue)
    if scenario == "initial_forensic":
        await assert_revoked_native_receipt_is_private(current, restarted, receipt)
        assert len(calls) == 1
        return
    assert (await restarted.inspect_committed(lease)).receipt == receipt
    await restarted.acknowledge(lease, receipt)
    async with primary_authority():
        session = value.guard._require_session()
        baseline = await session.get(SourcePublicationBaseline, receipt.source_attempt_id)
        origin = await session.get(SourceObject, value.admission.items[0].object_id)
        assert origin.published_local_revision == "cpv1:" + baseline.acknowledgement_sha256
        assert origin.published_native_version_id == receipt.file_version_id
        assert (await session.get(Job, lease.job_id)).status == "succeeded"
    if scenario == "replacement_admission":
        from sqlalchemy import text

        from koinon.knowledge.bulk.structured_dtos import DatasetReplacementBaseline
        from koinon.knowledge.bulk.structured_replacement import ReplacementMemberPlan

        previous = await dataset.identity(lease)
        replacement = previous.model_copy(
            update={
                "operation_id": uuid4(),
                "file_id": uuid4(),
                "catalog_file_version_id": str(uuid4()),
                "sha256": "b" * 64,
            }
        )
        predecessor = DatasetReplacementBaseline.model_validate(
            {
                "dataset_id": previous.dataset_id,
                "catalog_dataset_id": lease.asset_id,
                "source_attempt_id": receipt.source_attempt_id,
                "imported_version_id": receipt.source_attempt_id,
                "catalog_file_version_id": receipt.file_version_id,
                "policy_id": value.execution.policy_id,
                "local_revision": origin.published_local_revision,
                "source_generation": origin.generation,
                "policy_revision": value.admission.mapping_revision,
                "sha256": receipt.sha256,
                "native_file_id": receipt.native_file_id,
                "members": [
                    {
                        "member_key": "root",
                        "table_id": receipt.tables[0].table_id,
                        "catalog_table_id": receipt.tables[0].catalog_table_id,
                        "snapshot_id": receipt.tables[0].snapshot_id,
                        "source_file_id": receipt.native_file_id,
                        "local_revision": origin.published_local_revision,
                        "sha256": receipt.sha256,
                    }
                ],
            }
        )
        with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
            async with infrastructure_unit(native) as session:
                digest = await session.scalar(
                    text("SELECT public.koinon_json_sha256(CAST(:baseline AS jsonb))"),
                    {"baseline": predecessor.model_dump_json(by_alias=True)},
                )
            async with repository.write() as unit:
                admitted = await unit.admit_replacement(
                    replacement,
                    source_attempt_id=str(uuid4()),
                    baseline=predecessor,
                    baseline_sha256=digest,
                )
                assert admitted.baseline == predecessor and admitted.baseline_sha256 == digest
                planned = await unit.plan_replacement(
                    replacement,
                    tuple(
                        ReplacementMemberPlan(
                            member_key="root",
                            action="retain",
                            table_id=previous_table.table_id,
                            catalog_table_id=previous_table.catalog_table_id,
                            snapshot_id=uuid4(),
                            ordinal=0,
                            name="facts",
                        )
                        for previous_table in admitted.baseline.members
                    ),
                )
                assert len(planned.plan) == 1 and planned.plan[0].table_id == predecessor.members[0].table_id
    replacement_run = scenario.startswith("replacement_") and scenario != "replacement_admission"
    if replacement_run:
        from hashlib import sha256

        from koinon.integrations.content_sources.dtos import DownloadReceipt
        from koinon.integrations.content_sources.import_entities import SourceImportAttempt
        from koinon.integrations.content_sources.mapping_entities import SourceMapping
        from koinon.integrations.content_sources.settings import ContentSourceSettings
        from koinon.integrations.content_sources.sync_entities import SourceMappingPolicy, SourceSyncState
        from koinon.integrations.content_sources.sync_replacement import SourceReplacements
        from koinon.knowledge.content import ContentUpdates

        mappings = value.review.context.get_bean(SourceMappings)
        async with primary_authority():
            session = value.guard._require_session()
            mapping = await session.get(SourceMapping, value.admission.mapping_id)
            policy = await session.get(SourceMappingPolicy, value.execution.policy_id)
        capture = await mappings.remote_capture(lease.subject, lease.tenant_id, mapping, policy)
        async with primary_authority(read_only=False):
            await value.writer.authority.source_destination(value.admission)
            session = value.guard._require_session()
            assert await SourceRunRepository(session=session).finish(value.execution, capture=capture)
            revision = (await session.get(SourceSyncState, mapping.id)).revision
        value.changed["version"] = "v2"
        catalog = value.writer.authority.catalog
        private_only = catalog.get
        monkeypatch.setattr(catalog, "get", CatalogService.get.__get__(catalog, CatalogService))
        try:
            started = await mappings.execute(
                lease.subject, lease.tenant_id, mapping.id, "sync",
                SourceControlInput(operation_id=str(uuid4()), expected_revision=revision),
            )
        finally:
            monkeypatch.setattr(catalog, "get", private_only)
        async with primary_authority(read_only=False):
            await value.writer.authority.source_destination(value.admission)
            session = value.guard._require_session()
            next_lease = await SourceRunRepository(session=session).claim(
                lease.tenant_id, lease.subject, started.run_id, "replacement-worker"
            )
            state = await session.get(SourceSyncState, mapping.id)
            state.scan_max_items = value.review.context.get_bean(ContentSourceSettings).sync_max_scan_items
            state.scan_observed_count = 0
            state.revision += 1
            await session.flush()
            pins = await SourceCheckpoints(session=session).append(
                next_lease, 0,
                WalkPage((WalkItem(replace(value.remote_item, version="v2"), ("selected",)),), None, True, 1),
                cursor_ciphertext=None,
            )
        admission = replace(value.admission, run_id=next_lease.run_id, items=pins)
        original = mappings.browser._source
        downloads = []
        content = b"a\n5\n66\n"

        @asynccontextmanager
        async def remote(scope, token):
            async with original(scope, token) as adapter:
                async def download(item, sink, **options):
                    _no_remote_unit()
                    downloads.append(item.version)
                    await sink.write(content)
                    return DownloadReceipt(scope, item.item_id, item.version, len(content),
                                           sha256(content).hexdigest(), item.mime_type)
                adapter.download = download
                yield adapter

        monkeypatch.setattr(mappings.browser, "_source", remote)
        replacement = SourceReplacements(
            value.writer, mappings,
            SimpleNamespace(get=lambda: ContentUpdates(port.facade())),
            SimpleNamespace(get=lambda: current.files),
            structured=SimpleNamespace(get=lambda: pipeline),
        )
        if scenario != "replacement_execution":
            if scenario.startswith("replacement_native_admitted"):
                async def interrupt_original_storage(*args, **kwargs):
                    raise RuntimeError("native admission committed before original storage")

                with monkeypatch.context() as interrupted:
                    interrupted.setattr(LocalFsObjectStore, "put", interrupt_original_storage)
                    with pytest.raises(
                        RuntimeError, match="native admission committed before original storage"
                    ):
                        await replacement.execute(admission, next_lease)
            elif scenario in {"replacement_prepared_resume", "replacement_admission_resume"}:
                async def interrupt_prepared(*args, **kwargs):
                    raise RuntimeError("prepared replacement interrupted")

                with monkeypatch.context() as interrupted:
                    interrupted.setattr(
                        pipeline,
                        "finalize_replacement" if scenario == "replacement_prepared_resume"
                        else "prepare_replacement",
                        interrupt_prepared,
                    )
                    with pytest.raises(RuntimeError, match="prepared replacement interrupted"):
                        await replacement.execute(admission, next_lease)
            else:
                complete = value.guard.committed_replacement

                async def lose_acknowledgement(*args, **kwargs):
                    await complete(*args, **kwargs)
                    raise RuntimeError("acknowledgement transaction interrupted")

                with monkeypatch.context() as interrupted:
                    interrupted.setattr(value.guard, "committed_replacement", lose_acknowledgement)
                    with pytest.raises(RuntimeError, match="acknowledgement transaction interrupted"):
                        await replacement.execute(admission, next_lease)
            async with primary_authority(read_only=False):
                session = value.guard._require_session()
                pending = await session.scalar(select(SourceImportAttempt).where(
                    SourceImportAttempt.content_operation_id.is_not(None)
                ))
                baseline = await session.get(SourcePublicationBaseline, pending.id)
                assert baseline.acknowledgement_json is None and pending.receipt_json is None
                retained_members = baseline.descriptor_json["members"]
                origin = await session.get(SourceObject, pins[0].object_id)
                assert origin.published_native_version_id == receipt.file_version_id
                if scenario in {"replacement_membership", "replacement_membership_restored"}:
                    await session.execute(update(Membership).where(
                        Membership.id == lease.subject
                    ).values(role="viewer"))
                elif scenario == "replacement_aba":
                    from koinon.catalog.entities import CatalogEntry

                    row = await session.get(CatalogEntry, pending.asset_id)
                    original_name = row.name
                    await session.execute(update(CatalogEntry).where(
                        CatalogEntry.id == row.id
                    ).values(name="Local edit"))
                    await session.execute(update(CatalogEntry).where(
                        CatalogEntry.id == row.id
                    ).values(name=original_name))
            if scenario.startswith("replacement_native_admitted"):
                identity = await replacement._dataset_identity(admission, pending, baseline)
                with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
                    async with repository.read() as unit:
                        retained_native = await unit.get(identity)
                        assert retained_native.status == "admitted"
                        assert retained_native.source_attempt_id == pending.id
                        assert retained_native.source_publication_sha256 == baseline.descriptor_sha256
                        assert len(retained_native.replacement_plan) == 1
                assert len(calls) == 1
                if scenario != "replacement_native_admitted":
                    from flyquery.core.services.ingestion.stages.receive import original_object_key
                    from flyquery.models.entities.file import File

                    from koinon.knowledge.lineage.entities import SourceArtifactRow

                    key = original_object_key(
                        identity.tenant_id, identity.workspace_id, identity.dataset_id,
                        identity.file_id, identity.filename, "csv", "none",
                    )
                    store = pipeline.stores.get()
                    if scenario == "replacement_native_admitted_blob":
                        await store.put(key, content, "text/csv")
                    elif scenario == "replacement_native_admitted_unknown_head":
                        async def unknown_head(self, key):
                            raise OSError("Object metadata is temporarily unavailable")
                        monkeypatch.setattr(LocalFsObjectStore, "head", unknown_head)
                    else:
                        with native_scope(
                            "structured", lease.tenant_id, current.native_workspace, lease.subject
                        ):
                            async with repository.write() as unit:
                                scope = dict(
                                    tenant_id=identity.tenant_id, workspace_id=identity.workspace_id,
                                    dataset_id=identity.dataset_id,
                                )
                                if scenario == "replacement_native_admitted_file":
                                    row = File(
                                        id=identity.file_id, **scope, original_filename=identity.filename,
                                        file_format="csv", compression="none", size_bytes=len(content),
                                        content_hash_sha256=identity.sha256, object_store_key=key,
                                        uploaded_by=identity.actor, status="RECEIVED",
                                    )
                                elif scenario == "replacement_native_admitted_artifact":
                                    row = SourceArtifactRow(
                                        id=identity.file_id, **scope, actor=identity.actor,
                                        original_filename=identity.filename, sha256=identity.sha256,
                                        byte_size=len(content), file_format="csv", compression="none",
                                    )
                                else:
                                    member = retained_native.replacement_plan[0]
                                    row = SchemaSnapshot(
                                        id=member.snapshot_id, **scope, table_id=member.table_id,
                                        snapshot_hash="a" * 64, n_columns=1, status="PARTIAL",
                                        triggered_by="USER", created_by=identity.actor,
                                    )
                                unit._session.add(row)
                    writes = []
                    original_put = LocalFsObjectStore.put

                    async def record_put(self, key, body, content_type, **options):
                        writes.append(key)
                        return await original_put(self, key, body, content_type, **options)

                    monkeypatch.setattr(LocalFsObjectStore, "put", record_put)
                    outcome = await replacement.execute(admission, next_lease)
                    assert outcome.outcome == "unresolved"
                    assert (outcome.operation_id, outcome.attempt_id) == (
                        pending.content_operation_id, pending.id,
                    )
                    assert downloads == ["v2", "v2"] and len(calls) == 1 and not writes
                    if scenario == "replacement_native_admitted_blob":
                        assert b"".join([part async for part in await store.get(key)]) == content
                    async with primary_authority():
                        session = value.guard._require_session()
                        header = await session.get(SourcePublicationBaseline, pending.id)
                        origin = await session.get(SourceObject, pins[0].object_id)
                        assert header.acknowledgement_json is None
                        assert header.descriptor_json["members"] == retained_members
                        assert origin.published_native_version_id == receipt.file_version_id
                    with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
                        async with repository.read() as unit:
                            assert await unit.get(identity) == retained_native
                    return
        outcome = await replacement.execute(admission, next_lease)
        forensic = scenario in {
            "replacement_membership", "replacement_membership_restored", "replacement_aba"
        }
        assert outcome.outcome == ("conflict" if forensic else "acknowledged")
        assert outcome.attempt_id and outcome.operation_id
        expected_downloads = (
            ["v2", "v2"]
            if scenario in {"replacement_admission_resume", "replacement_native_admitted"}
            else ["v2"]
        )
        assert downloads == expected_downloads and len(calls) == 2
        if scenario != "replacement_execution":
            assert outcome.attempt_id == pending.id
            assert outcome.operation_id == pending.content_operation_id
        async with primary_authority():
            session = value.guard._require_session()
            attempt = await session.get(SourceImportAttempt, outcome.attempt_id)
            header = await session.get(SourcePublicationBaseline, attempt.id)
            assert header.previous_attempt_id == receipt.source_attempt_id
            assert attempt.receipt_json["native_file_id"] != receipt.native_file_id
            assert attempt.receipt_json["tables"][0]["table_id"] == receipt.tables[0].table_id
            assert attempt.receipt_json["tables"][0]["snapshot_id"] != receipt.tables[0].snapshot_id
            if scenario != "replacement_execution":
                assert header.descriptor_json["members"] == retained_members
                assert [
                    (table["catalog_table_id"], table["table_id"], table["snapshot_id"])
                    for table in attempt.receipt_json["tables"]
                ] == [
                    (member["catalog_table_id"], member["table_id"], member["snapshot_id"])
                    for member in retained_members if member["action"] != "remove"
                ]
            origin = await session.get(SourceObject, pins[0].object_id)
            if forensic:
                assert header.acknowledgement_json is None
                assert origin.published_native_version_id == receipt.file_version_id
            else:
                assert header.acknowledgement_json["native_receipt"]["native_file_id"] == (
                    attempt.receipt_json["native_file_id"]
                )
                assert origin.published_local_revision == "cpv1:" + header.acknowledgement_sha256
        assert await replacement.execute(admission, next_lease) == outcome
        assert downloads == expected_downloads and len(calls) == 2
        if scenario == "replacement_membership_restored":
            original_digest = header.descriptor_sha256
            original_receipt = dict(attempt.receipt_json)
            async with primary_authority(read_only=False):
                session = value.guard._require_session()
                await session.execute(
                    update(Membership).where(Membership.id == lease.subject).values(role="admin")
                )
            acknowledged = await replacement.execute(admission, next_lease)
            assert acknowledged.outcome == "acknowledged" and acknowledged.attempt_id == pending.id
            async with primary_authority():
                session = value.guard._require_session()
                header = await session.get(SourcePublicationBaseline, pending.id)
                attempt = await session.get(SourceImportAttempt, pending.id)
                assert header.descriptor_sha256 == original_digest and header.acknowledgement_json is not None
                assert attempt.receipt_json == original_receipt
            assert await replacement.execute(admission, next_lease) == acknowledged
            assert downloads == ["v2"] and len(calls) == 2
    with native_scope("structured", lease.tenant_id, current.native_workspace, lease.subject):
        async with infrastructure_unit(native) as session:
            assert (
                await session.scalar(
                    select(func.count()).select_from(SchemaSnapshot).where(SchemaSnapshot.status == "READY")
                )
                == (2 if replacement_run else 1)
            )
            assert (
                await session.scalar(
                    select(func.count()).select_from(SchemaObject).where(SchemaObject.embedding.is_not(None))
                )
                == (4 if replacement_run else 2)
            )
    assert len(calls) == (2 if replacement_run else 1)
