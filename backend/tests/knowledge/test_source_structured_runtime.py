# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product query preparation and identity hydration against owned PostgreSQL."""

import asyncio
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic import command
from flyquery.core.services.query import provenance
from flyquery.core.services.query.dtos import AnswerResult
from flyquery.core.services.query.prepared import PreparedQuery
from flyquery.core.services.query.query_repository import QueryRepository
from flyquery.core.services.retrieval.search_index import ProductSearchIndex
from flyquery.data import StructuredSessionBinding
from flyquery.models.entities import (
    Dataset,
    Query,
    QueryResult,
    SchemaObject,
    SchemaSnapshot,
    Table,
    Workspace,
)
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import current_unit_of_work, infrastructure_unit
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import event, select

from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
from koinon.knowledge.bulk_queries.native_entities import NativeQueryOperation
from koinon.knowledge.bulk_queries.native_repository import NativeQueryUnit, receipt_of
from koinon.knowledge.bulk_queries.native_values import QueryOperationIdentity

pytestmark = pytest.mark.integration

_fixture_spec = importlib.util.spec_from_file_location(
    "structured_owned_source_database",
    Path(__file__).parents[1] / "integrations/content_sources/test_source_migration_postgres.py",
)
_fixture_module = importlib.util.module_from_spec(_fixture_spec)
_fixture_spec.loader.exec_module(_fixture_module)
source_database = _fixture_module.source_database


def policy():
    from flycanon.config import CanonSettings
    from flyquery.config import FlyquerySettings

    from koinon.organization_knowledge.dtos import (
        DocumentKnowledgeSettings,
        OrganizationKnowledgeSnapshot,
        StructuredKnowledgeSettings,
        snapshot_digest,
    )

    documents, structured = CanonSettings(), FlyquerySettings()
    values = {
        "tenant_id": "retained",
        "schema_version": 1,
        "revision": 0,
        "origin": "deployment",
        "documents": {
            **{
                name: getattr(documents, name)
                for name in DocumentKnowledgeSettings.model_fields
                if name not in {"answer_top_k", "rlm_extended_reasoning"}
            },
            "answer_top_k": 10,
            "rlm_extended_reasoning": False,
        },
        "structured": {name: getattr(structured, name) for name in StructuredKnowledgeSettings.model_fields},
    }
    return OrganizationKnowledgeSnapshot.model_validate({**values, "digest": snapshot_digest(values)})


@pytest.fixture
async def structured_database(source_database):
    from koinon.knowledge.bulk.repositories import BulkRepository
    from koinon.knowledge.bulk_queries.repositories import QueryBatchRepository

    target, _, engine = source_database
    _fixture_module.upgrade_sources(engine)
    with engine.connect() as connection:
        config = _fixture_module.load("deploy/migrate.py").history_config(
            "structured",
            Path(__file__).resolve().parents[3] / "packages/structured/migrations/versions",
            connection,
        )
        command.upgrade(config, "head")
        connection.commit()
    url = target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": url,
                            "datasources": {"structured": {"url": url, "ddl-auto": "none"}},
                        }
                    }
                }
            }
        )
    )
    context.register_bean(BulkRepository)
    context.register_bean(QueryBatchRepository)
    await context.start()
    registry = context.get_bean(DataSourceRegistry)
    source = registry.get("structured")
    workspace, dataset, table, snapshot, schema = (uuid4() for _ in range(5))
    async with source.engine.begin() as connection:
        await connection.execute(
            Workspace.__table__.insert().values(
                id=workspace, tenant_id="retained", slug="workspace", name="Workspace"
            )
        )
        await connection.execute(
            Dataset.__table__.insert().values(
                id=dataset, tenant_id="retained", workspace_id=workspace, name="Dataset"
            )
        )
        await connection.execute(
            Table.__table__.insert().values(
                id=table,
                tenant_id="retained",
                workspace_id=workspace,
                dataset_id=dataset,
                name="orders",
                qualified_name="orders",
                current_snapshot_id=snapshot,
            )
        )
        await connection.execute(
            SchemaSnapshot.__table__.insert().values(
                id=snapshot,
                tenant_id="retained",
                workspace_id=workspace,
                dataset_id=dataset,
                table_id=table,
                snapshot_hash="a" * 64,
                n_columns=1,
                parquet_object_key="private/orders.parquet",
                status="READY",
                triggered_by="USER",
                created_by="reader",
            )
        )
        await connection.execute(
            SchemaObject.__table__.insert().values(
                id=schema,
                tenant_id="retained",
                workspace_id=workspace,
                table_id=table,
                snapshot_id=snapshot,
                kind="COLUMN",
                qualified_name="orders.total",
                description="Protected amount",
                data_type="INTEGER",
                source_hash="a" * 64,
                profile_json={},
                sample_values_json=[13],
                governance_json={},
            )
        )
    try:
        yield SimpleNamespace(
            source=source,
            registry=registry,
            workspace=workspace,
            dataset=dataset,
            table=table,
            snapshot=snapshot,
            schema=schema,
            context=context,
        )
    finally:
        await context.stop()


@pytest.mark.parametrize("denied", [False, True])
async def test_pg_schema_authority_closes_identity_unit_and_never_substitutes_new_pointer(
    structured_database, denied
):
    fixture = structured_database
    statements = []

    def sql(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(fixture.source.engine.sync_engine, "before_cursor_execute", sql)

    class Observer:
        def scope(self, *args):
            pass

        async def structured_admission(self, kind, rows, scope):
            assert current_unit_of_work() is None
            assert rows, "The exact retained schema must remain available for admission"
            assert kind == "schema" and rows[0]["snapshot_id"] == fixture.snapshot
            if denied:
                return ()
            async with fixture.source.engine.begin() as connection:
                await connection.execute(
                    Table.__table__.update()
                    .where(Table.id == fixture.table)
                    .values(current_snapshot_id=uuid4())
                )
                await connection.execute(
                    SchemaObject.__table__.update()
                    .where(SchemaObject.id == fixture.schema)
                    .values(is_active=False)
                )
            return rows

    try:
        with provenance.observe(
            Observer(),
            tenant_id="retained",
            workspace_id=fixture.workspace,
            dataset_id=fixture.dataset,
            actor="reader",
        ):
            rows = await ProductSearchIndex(fixture.source.sessionmaker).all_schema_objects(fixture.dataset)
            if not denied:
                historical = ProductSearchIndex(fixture.source.sessionmaker)
                historical.bind_snapshot_pins({"orders": str(fixture.snapshot)})
                prior = await historical.all_schema_objects(fixture.dataset)
                assert [row.id for row in prior] == [row.id for row in rows]
        if denied:
            assert rows == []
            assert not any("o.description" in statement for statement in statements)
        else:
            assert len(rows) == 1 and rows[0].metadata["snapshot_id"] == str(fixture.snapshot)
            assert "Protected amount" in rows[0].text
        assert current_unit_of_work() is None
    finally:
        event.remove(fixture.source.engine.sync_engine, "before_cursor_execute", sql)


@pytest.mark.parametrize("denied", [False, True])
async def test_pg_source_admission_supplies_only_exact_snapshot_identity_outside_units(
    structured_database, denied
):
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
    from koinon.knowledge.native_provenance import bind_structured_source

    fixture = structured_database
    checked = []
    receipt = NativeEvidenceReceipt("reader", "retained")
    operation = SimpleNamespace(tenant="retained", actor="reader", used=())

    class Reader:
        async def sources(self, actor, tenant, references, *, operation):
            assert all(current_unit_of_work(name) is None for name in (None, "primary", "structured"))
            assert (actor, tenant) == ("reader", "retained")
            assert len(references) == 1
            assert references[0].snapshot_id == str(fixture.snapshot)
            assert references[0].asset_id == "canonical-dataset"
            checked.extend(references)
            if denied:
                raise SourceError("access_denied")

    operation.reader = Reader()
    bind_structured_source(
        receipt,
        operation,
        "canonical-dataset",
        SimpleNamespace(
            native_id=str(fixture.dataset),
            native_workspace_id=str(fixture.workspace),
        ),
    )
    with provenance.observe(
        receipt,
        tenant_id="retained",
        workspace_id=fixture.workspace,
        dataset_id=fixture.dataset,
        actor="reader",
    ):
        if denied:
            with pytest.raises(SourceError):
                await ProductSearchIndex(fixture.source.sessionmaker).all_schema_objects(fixture.dataset)
        else:
            rows = await ProductSearchIndex(fixture.source.sessionmaker).all_schema_objects(fixture.dataset)
            assert len(rows) == 1
    assert len(checked) == 1
    assert receipt.structured_source_manifest == (
        {} if denied else {str(fixture.table): str(fixture.snapshot)}
    )


async def test_pg_canonical_schema_hydrates_the_admitted_version_after_pointer_replacement(
    structured_database,
):
    from flyquery.core.services.tables.schema_snapshot_repository import SchemaSnapshotRepository
    from flyquery.core.services.tables.table_repository import TableRepository
    from flyquery.core.services.tables.table_service import TableService

    from koinon.knowledge.adapters import NativeDomains
    from koinon.knowledge.capture_receipt import NativeEvidenceReceipt

    fixture = structured_database
    replacement = uuid4()
    async with fixture.source.engine.begin() as connection:
        await connection.execute(
            SchemaSnapshot.__table__.insert().values(
                id=replacement,
                tenant_id="retained",
                workspace_id=fixture.workspace,
                dataset_id=fixture.dataset,
                table_id=fixture.table,
                snapshot_hash="b" * 64,
                n_columns=1,
                parquet_object_key="private/replacement.parquet",
                status="READY",
                triggered_by="USER",
                created_by="reader",
            )
        )
        await connection.execute(
            SchemaObject.__table__.insert().values(
                id=uuid4(),
                tenant_id="retained",
                workspace_id=fixture.workspace,
                table_id=fixture.table,
                snapshot_id=replacement,
                kind="COLUMN",
                qualified_name="orders.replacement_secret",
                source_hash="b" * 64,
                data_type="TEXT",
                profile_json={},
                sample_values_json=[],
                governance_json={},
            )
        )

    async def replace_pointer():
        assert current_unit_of_work() is None
        async with fixture.source.engine.begin() as connection:
            await connection.execute(
                Table.__table__.update()
                .where(Table.id == fixture.table)
                .values(current_snapshot_id=replacement)
            )

    sessions = StructuredSessionBinding(fixture.source.sessionmaker)

    class ReplacingTables(TableService):
        async def list_for_dataset(self, *args, **kwargs):
            rows = await super().list_for_dataset(*args, **kwargs)
            await replace_pointer()
            return rows

    tables = ReplacingTables(TableRepository(sessions), SchemaSnapshotRepository(sessions))
    admitted = []

    async def admit(kind, rows, scope):
        assert kind == "table"
        assert rows[0]["snapshot_id"] == fixture.snapshot
        admitted.extend(rows)
        await replace_pointer()
        return rows

    receipt = NativeEvidenceReceipt("reader", "retained")
    receipt.structured_admission = admit
    receipt.structured_source_operation = SimpleNamespace()
    domains = NativeDomains.__new__(NativeDomains)
    domains._resolve = lambda bean: fixture.registry if bean is DataSourceRegistry else tables
    result = await domains.schema(
        tenant_id="retained",
        workspace_id=str(fixture.workspace),
        dataset_id=str(fixture.dataset),
        actor="reader",
        _capture=receipt,
    )
    assert result["tables"][0]["snapshot_id"] == str(fixture.snapshot)
    assert [column["name"] for column in result["tables"][0]["columns"]] == ["total"]
    assert [row["snapshot_id"] for row in admitted] == [fixture.snapshot]
    assert current_unit_of_work() is None


def prepared_answer(fixture, status="OK"):
    prepared = PreparedQuery()
    fields = dict(
        tenant_id="retained",
        workspace_id=fixture.workspace,
        dataset_id=fixture.dataset,
        question="Count",
        semantic_path_taken="SYNTHESIS",
        candidates_json=[],
        chosen_candidate_index=0,
        executed_sql="SELECT 1",
        ast_classification="SELECT",
        execution_status=status,
        retries=0,
        row_count=1,
        elapsed_ms=1,
        clarification_emitted=False,
        clarification_json=None,
        pii_findings_json=None,
        error_json=None,
        query_id=prepared.query_id,
    )
    prepared.stage("query", fields)
    prepared.stage(
        "result",
        dict(
            query_id=prepared.query_id,
            tenant_id="retained",
            workspace_id=fixture.workspace,
            result_preview_json=[{"value": 1}],
            result_object_key=None,
            result_byte_size=None,
        ),
    )
    prepared.seal(
        AnswerResult(
            query_id=prepared.query_id,
            sql="SELECT 1",
            execution_status=status,
            preview=[{"value": 1}],
            row_count=1,
            truncated=False,
            elapsed_ms=1,
            chart_hint=None,
            explanation=None,
            clarification=None,
            grounded_summary=None,
        )
    )
    prepared.bind_manifest({str(fixture.table): str(fixture.snapshot)})
    return prepared


async def test_pg_product_conversation_pins_also_govern_kind_and_path_resolution(structured_database):
    from flyquery.config import FlyquerySettings
    from flyquery.core.services.execution.table_resolver import ProductTableResolver

    fixture = structured_database
    async with fixture.source.engine.begin() as connection:
        await connection.execute(
            Table.__table__.update().where(Table.id == fixture.table).values(current_snapshot_id=uuid4())
        )
    snapshots = []

    class Observer:
        def scope(self, *args):
            pass

        async def structured_admission(self, kind, rows, scope):
            snapshots.extend(row["snapshot_id"] for row in rows)
            return rows

        def structured_resolved(self, rows, scope):
            pass

    resolver = ProductTableResolver(fixture.source.sessionmaker, FlyquerySettings())
    assert hasattr(resolver, "bind_snapshot_pins")
    resolver.bind_snapshot_pins({"orders": str(fixture.snapshot)})
    with provenance.observe(
        Observer(),
        tenant_id="retained",
        workspace_id=fixture.workspace,
        dataset_id=fixture.dataset,
        actor="reader",
    ):
        kinds = await resolver.list_kinds_for_dataset_by_names(fixture.dataset, ["orders"])
        paths = await resolver.resolve(fixture.dataset, ["orders"])
    assert kinds == [{"name": "orders", "kind": "UPLOADED"}]
    assert paths["orders"].endswith("private/orders.parquet")
    assert snapshots == [fixture.snapshot, fixture.snapshot]


@pytest.mark.parametrize("failure", [None, RuntimeError, asyncio.CancelledError])
async def test_pg_prepared_query_result_and_receipt_share_one_explicit_native_commit(
    structured_database, failure
):
    fixture = structured_database
    repository = QueryRepository(StructuredSessionBinding(fixture.source.sessionmaker))
    prepared = prepared_answer(fixture)
    selected = policy()
    identity = QueryOperationIdentity(
        operation_id=uuid4(),
        tenant_id="retained",
        subject="reader",
        workspace_id=fixture.workspace,
        dataset_id=fixture.dataset,
        catalog_workspace_id="workspace",
        catalog_dataset_id="dataset",
        question="Count",
        policy_sha256=selected.digest,
        connections_sha256="a" * 64,
    )
    value = BatchQueryOutcome(
        query_id=prepared.query_id,
        execution_status="OK",
        sql="SELECT 1",
        preview=[{"value": 1}],
        row_count=1,
        elapsed_ms=1,
        knowledge_settings_snapshot=selected,
        snapshot_pins={"orders": str(fixture.snapshot)},
    )
    async with infrastructure_unit(fixture.source) as session:
        await NativeQueryUnit(session).admit(identity)
    assert await repository.prepared_reference(prepared.query_id) is None

    async def publish():
        async with infrastructure_unit(fixture.source) as session:
            answer = await prepared.publish(repository, None, None)
            assert answer.query_id == prepared.query_id
            assert (
                await session.scalar(select(Query.id).where(Query.id == prepared.query_id))
                == prepared.query_id
            )
            assert (
                await session.scalar(
                    select(QueryResult.query_id).where(QueryResult.query_id == prepared.query_id)
                )
                == prepared.query_id
            )
            receipt = await NativeQueryUnit(session).commit(identity, value)
            assert receipt.result.query_id == prepared.query_id
            assert receipt.snapshots[0].snapshot_id == fixture.snapshot
            assert receipt.source_manifest == {str(fixture.table): str(fixture.snapshot)}
            if failure:
                raise failure("receipt insertion failed")

    if failure:
        with pytest.raises(failure):
            await publish()
        assert await repository.prepared_reference(prepared.query_id) is None
        async with infrastructure_unit(fixture.source, read_only=True) as session:
            assert receipt_of(await NativeQueryUnit(session).row(identity)) is None
    else:
        await publish()
        assert (await repository.prepared_reference(prepared.query_id))["id"] == prepared.query_id
        async with fixture.source.sessionmaker() as session:
            assert await session.scalar(
                select(Query.table_id_snapshot_pins_json).where(Query.id == prepared.query_id)
            ) == {str(fixture.table): str(fixture.snapshot)}
            operation = await session.get(NativeQueryOperation, identity.operation_id)
            assert receipt_of(operation).result == value
    with pytest.raises(ServiceUnavailableException, match="expired"):
        async with infrastructure_unit(fixture.source):
            await prepared.publish(repository, None, None)


@pytest.fixture
async def committed_query(structured_database, request):
    fixture = structured_database
    from koinon.knowledge.bulk_queries.native_repository import NativeQueryRepository

    repository = QueryRepository(StructuredSessionBinding(fixture.source.sessionmaker))
    status = getattr(request, "param", "OK")
    prepared = prepared_answer(fixture, status)
    identity = QueryOperationIdentity(
        operation_id=uuid4(),
        tenant_id="retained",
        subject="reader",
        workspace_id=fixture.workspace,
        dataset_id=fixture.dataset,
        catalog_workspace_id="workspace",
        catalog_dataset_id="dataset",
        question="Count",
        policy_sha256=policy().digest,
        connections_sha256="a" * 64,
    )
    result = BatchQueryOutcome(
        query_id=prepared.query_id,
        execution_status=status,
        sql="SELECT 1",
        preview=[{"value": 1}],
        row_count=1,
        elapsed_ms=1,
        knowledge_settings_snapshot=policy(),
        snapshot_pins={"orders": str(fixture.snapshot)},
    )
    native = NativeQueryRepository(SimpleNamespace(native=lambda: fixture.source))
    async with native.write() as unit:
        await unit.admit(identity)
        await prepared.publish(repository, None, None)
        receipt = await unit.commit(identity, result)
    return fixture, native, identity, receipt


async def test_pg_commit_metadata_projects_only_identity_status_and_hashes(committed_query):
    fixture, native, identity, receipt = committed_query
    projections = []

    def after(connection, cursor, statement, parameters, context, executemany):
        if cursor.description:
            projections.append(tuple(column[0] for column in cursor.description))

    event.listen(fixture.source.engine.sync_engine, "after_cursor_execute", after)
    try:
        status, descriptor = await native.inspect_commit_metadata(identity)
    finally:
        event.remove(fixture.source.engine.sync_engine, "after_cursor_execute", after)
    assert status == "committed"
    assert descriptor.query_id == receipt.result.query_id
    assert descriptor.operation_id == identity.operation_id
    assert descriptor.outcome == "succeeded"
    assert len(descriptor.receipt_sha256) == len(descriptor.manifest_sha256) == 64
    assert projections == [
        (
            "status",
            "valid",
            "operation_id",
            "query_id",
            "identity_sha256",
            "receipt_sha256",
            "manifest_sha256",
            "outcome",
        )
    ]
    from pyfly.kernel import ConflictException

    with pytest.raises(ConflictException):
        await native.inspect_commit_metadata(identity.model_copy(update={"question": "Different"}))


@pytest.mark.parametrize(
    "committed_query", ["OK", "REFINED_OK", "FAILED", "REJECTED_BY_FIREWALL"], indirect=True
)
async def test_pg_terminal_query_projection_matches_immutable_commit_manifest(committed_query):
    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_native import SourceReadNative

    fixture, native, identity, receipt = committed_query
    binding = SimpleNamespace(native_workspace_id=str(fixture.workspace), native_id=str(fixture.dataset))
    status, descriptor = await native.inspect_commit_metadata(identity)
    projection = await SourceReadNative().terminal_query_manifest(
        "reader", "retained", binding, str(receipt.result.query_id)
    )
    assert projection.query_id == descriptor.query_id
    assert projection.manifest_sha256 == descriptor.manifest_sha256
    assert projection.source_manifest == {str(fixture.table): str(fixture.snapshot)}
    if projection.execution_status in {"FAILED", "REJECTED_BY_FIREWALL"}:
        with pytest.raises(SourceError):
            await SourceReadNative().query_snapshots("reader", "retained", binding, str(projection.query_id))
    else:
        assert await SourceReadNative().query_snapshots(
            "reader", "retained", binding, str(projection.query_id)
        ) == {str(fixture.snapshot)}
    with pytest.raises(SourceError):
        await SourceReadNative().terminal_query_manifest(
            "reader", "different", binding, str(projection.query_id)
        )


@pytest.mark.parametrize("denial", [None, "admission", "release"])
async def test_pg_recovered_result_requires_exact_reader_manifest_before_hydration_and_output(
    committed_query, denial
):
    from unittest.mock import AsyncMock

    from koinon.integrations.content_sources.errors import SourceError
    from koinon.integrations.content_sources.read_native import SourceReadNative
    from koinon.knowledge.bulk_queries.native import BulkQueryNative
    from koinon.knowledge.bulk_queries.service import QueryBatches

    fixture, repository, identity, receipt = committed_query
    _, descriptor = await repository.inspect_commit_metadata(identity)
    operation = SimpleNamespace(actor="reader", tenant="retained")
    admitted = []

    async def sources(actor, tenant, refs, *, operation):
        assert current_unit_of_work() is None
        if denial == "admission":
            raise SourceError("access_denied")
        admitted.extend(ref.snapshot_id for ref in refs)

    async def release():
        assert current_unit_of_work() is None
        if denial == "release":
            raise SourceError("access_denied")

    reader = SimpleNamespace(
        native=SimpleNamespace(get=lambda: SourceReadNative()),
        sources=sources,
        begin=AsyncMock(return_value=operation),
    )
    operation.reader, operation.release = reader, release
    facade = SimpleNamespace(source_reader=SimpleNamespace(get=lambda: reader))
    authority = SimpleNamespace(facade=lambda: facade)
    native = BulkQueryNative(repository, None, None, authority)
    batches = QueryBatches(None, authority, None, None, native, None)
    batches._guard = AsyncMock()
    state = SimpleNamespace(
        dataset_id="dataset",
        query_id=str(descriptor.query_id),
        native_commit_json=descriptor.model_dump(mode="json", by_alias=True),
        native_identity=identity,
        status="succeeded",
        error_code=None,
        native_workspace_id=str(fixture.workspace),
        native_dataset_id=str(fixture.dataset),
    )
    hydrated = []

    def after(connection, cursor, statement, parameters, context, executemany):
        if cursor.description and "receipt_json" in tuple(c[0] for c in cursor.description):
            hydrated.append(True)

    event.listen(fixture.source.engine.sync_engine, "after_cursor_execute", after)
    try:
        if denial:
            with pytest.raises(SourceError):
                await batches._descriptor_result(
                    "reader", "retained", "batch", str(identity.operation_id), state, reader
                )
        else:
            result = await batches._descriptor_result(
                "reader", "retained", "batch", str(identity.operation_id), state, reader
            )
            assert result.result == receipt.result
        assert admitted == ([] if denial == "admission" else [str(fixture.snapshot)])
        assert bool(hydrated) is (denial != "admission")
    finally:
        event.remove(fixture.source.engine.sync_engine, "after_cursor_execute", after)


@pytest.mark.parametrize("cancelled", [False, True])
async def test_pg_metadata_acknowledgement_settles_same_commit_after_revocation_without_result_or_aliases(
    committed_query, cancelled
):
    from dataclasses import replace
    from datetime import timedelta
    from unittest.mock import AsyncMock

    from pyfly.kernel import ConflictException
    from sqlalchemy import func

    from koinon.catalog.entities import CatalogEntry
    from koinon.jobs.entities import Job
    from koinon.knowledge.bulk.entities import now
    from koinon.knowledge.bulk.repositories import BulkRepository
    from koinon.knowledge.bulk_queries.entities import QueryBatch, QueryBatchItem, QueryBatchReference
    from koinon.knowledge.bulk_queries.native import BulkQueryNative
    from koinon.knowledge.bulk_queries.queue import QueryLease
    from koinon.knowledge.bulk_queries.repositories import QueryBatchRepository

    fixture, operations, identity, receipt = committed_query
    item_id, batch_id, job_id = str(identity.operation_id), str(uuid4()), str(uuid4())
    lease = QueryLease(
        job_id,
        item_id,
        batch_id,
        "retained",
        "reader",
        None,
        "worker",
        1,
        "workspace",
        "dataset",
        str(fixture.workspace),
        str(fixture.dataset),
        "Count",
        policy(),
        "a" * 64,
        now() + timedelta(minutes=5),
    )
    async with infrastructure_unit(fixture.registry.primary) as session:
        session.add(
            CatalogEntry(
                id="workspace",
                tenant_id="retained",
                workspace_id="workspace",
                kind="workspace",
                name="Workspace",
                created_by="reader",
            )
        )
        await session.flush()
        session.add(
            CatalogEntry(
                id="dataset",
                tenant_id="retained",
                workspace_id="workspace",
                parent_id="workspace",
                kind="dataset",
                name="Dataset",
                created_by="reader",
            )
        )
        session.add(
            Job(
                id=job_id,
                tenant_id="retained",
                resource_id="dataset",
                kind="knowledge.bulk.query",
                idempotency_key=job_id,
                payload_hash="b" * 64,
                payload={"batch_id": batch_id, "item_id": item_id},
                status="cancelled" if cancelled else "running",
                attempts=1,
                worker_id=None if cancelled else "worker",
                lease_until=lease.expires_at,
            )
        )
        session.add(
            QueryBatch(
                id=batch_id,
                tenant_id="retained",
                workspace_id="workspace",
                subject="reader",
                key_hash="b" * 64,
                request_hash="c" * 64,
                request_json={},
                cancelled=cancelled,
                expires_at=lease.expires_at,
            )
        )
        await session.flush()
        session.add(
            QueryBatchItem(
                id=item_id,
                batch_id=batch_id,
                ordinal=0,
                client_item_id="one",
                dataset_id="dataset",
                question="Count",
                native_workspace_id=str(fixture.workspace),
                native_dataset_id=str(fixture.dataset),
                connection_json={},
                policy_json=policy().model_dump(mode="json"),
                job_id=job_id,
                status="reconciling" if cancelled else "running",
            )
        )
    records = fixture.context.get_bean(QueryBatchRepository)
    authority = SimpleNamespace(
        shared=fixture.context.get_bean(BulkRepository),
        workspace=AsyncMock(side_effect=PermissionError("Reader revoked")),
        item=AsyncMock(side_effect=PermissionError("Reader revoked")),
    )
    native = BulkQueryNative(operations, None, records, authority)
    _, descriptor = await native.inspect_commit_metadata(lease)
    with pytest.raises(ConflictException):
        await native.acknowledge_commit_metadata(replace(lease, attempt=0), descriptor)
    with pytest.raises(ConflictException):
        await native.acknowledge_commit_metadata(
            lease, descriptor.model_copy(update={"receipt_sha256": "f" * 64})
        )
    projections = []

    def after(connection, cursor, statement, parameters, context, executemany):
        if cursor.description:
            projections.extend(column[0] for column in cursor.description)

    event.listen(fixture.source.engine.sync_engine, "after_cursor_execute", after)
    event.listen(fixture.registry.primary.engine.sync_engine, "after_cursor_execute", after)
    try:
        await native.acknowledge_commit_metadata(lease, descriptor)
        await native.acknowledge_commit_metadata(lease, descriptor)
    finally:
        event.remove(fixture.source.engine.sync_engine, "after_cursor_execute", after)
        event.remove(fixture.registry.primary.engine.sync_engine, "after_cursor_execute", after)
    assert (
        "receipt_json" not in projections
        and "result_json" not in projections
        and "qualified_name" not in projections
    )
    async with infrastructure_unit(fixture.registry.primary, read_only=True) as session:
        item = await session.get(QueryBatchItem, item_id)
        assert item.status == "succeeded" and item.result_json is None
        assert item.native_commit_json == descriptor.model_dump(mode="json", by_alias=True)
        assert await session.scalar(select(func.count()).select_from(QueryBatchReference)) == 0
        assert (await session.get(QueryBatch, batch_id)).cancelled is cancelled
    authority.workspace.assert_not_awaited()
    authority.item.assert_not_awaited()


@pytest.mark.parametrize("denial", [None, "remote", "local", "bulk", "receipt", "release"])
async def test_pg_product_publication_orders_fences_and_retains_committed_artifact(
    structured_database, denial
):
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from koinon.knowledge.adapters import NativeDomains

    fixture = structured_database
    prepared = prepared_answer(fixture)
    key = f"private/{prepared.query_id}.parquet"
    prepared.artifacts.add(key)
    repository = QueryRepository(StructuredSessionBinding(fixture.source.sessionmaker))
    events = []
    store = SimpleNamespace(delete=AsyncMock())
    domains = NativeDomains.__new__(NativeDomains)
    domains._resolve = lambda bean: fixture.registry if bean is DataSourceRegistry else store

    def outside():
        assert all(current_unit_of_work(name) is None for name in (None, "primary", "structured", "canon"))

    def deny(stage):
        if denial == stage:
            raise ServiceUnavailableException(stage)

    class Operation:
        releases = 0

        async def release(self):
            outside()
            self.releases += 1
            stage = "release" if self.releases == 2 else "remote"
            events.append(stage)
            deny(stage)

        @asynccontextmanager
        async def local_fence(self):
            outside()
            async with infrastructure_unit(fixture.registry.primary):
                events.append("source-local")
                yield

    async def local():
        assert current_unit_of_work("primary") is not None
        assert current_unit_of_work("structured") is None
        events.append("local")
        deny("local")

    @asynccontextmanager
    async def bulk():
        assert current_unit_of_work("primary") is not None
        assert current_unit_of_work("structured") is None
        events.append("bulk")
        deny("bulk")
        yield

    async def authorize():
        outside()
        events.append("authorize")

    async def commit(value):
        assert current_unit_of_work("primary") is not None
        assert current_unit_of_work("structured") is not None
        events.append("receipt")
        deny("receipt")

    receipt = SimpleNamespace(
        authorize=authorize,
        structured_source_manifest={str(fixture.table): str(fixture.snapshot)},
    )
    if denial:
        with pytest.raises(ServiceUnavailableException, match=denial):
            await domains._publish_source_query(
                prepared, repository, receipt, Operation(), local, commit=commit, publication_guard=bulk
            )
    else:
        answer = await domains._publish_source_query(
            prepared, repository, receipt, Operation(), local, commit=commit, publication_guard=bulk
        )
        assert answer.query_id == prepared.query_id
    outside()
    retained = await repository.prepared_reference(prepared.query_id)
    assert bool(retained) is (denial in (None, "release"))
    if retained:
        store.delete.assert_not_awaited()
    else:
        store.delete.assert_awaited_once_with(key)
    expected = ["authorize", "remote", "source-local", "local", "bulk", "receipt", "release"]
    assert events == (expected[: expected.index(denial) + 1] if denial else expected)
    async with infrastructure_unit(fixture.source):
        with pytest.raises(ServiceUnavailableException, match="expired"):
            await prepared.publish(repository, None, None)
    with pytest.raises(ServiceUnavailableException, match="expired"):
        prepared.seal(prepared.answer)
