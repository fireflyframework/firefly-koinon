# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Whole-file source replacement preserves old state until guarded publication."""

import hashlib
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from pyfly.kernel import ConflictException

from koinon.knowledge.bulk.structured_dtos import PreparedStructuredTable


@pytest.mark.parametrize("field", ["qualified_name", "sheet_or_json_path"])
def test_prepared_parser_metadata_has_utf8_byte_bounds(field):
    values = dict(
        ordinal=0,
        table_id=uuid4(),
        snapshot_id=uuid4(),
        name="facts",
        catalog_table_id="catalog",
        lineage_run_id=uuid4(),
        n_columns=1,
        n_rows_actual=1,
        parquet_key="private",
        parquet_sha256="a" * 64,
        parquet_byte_size=1,
        schema_sha256="b" * 64,
    )
    with pytest.raises(ValidationError):
        PreparedStructuredTable(**values, **{field: "é" * 1025})


async def test_prepared_replacement_restores_exact_predecessor_lineage():
    from koinon.integrations.content_sources.source_structured import StructuredSourceProducer

    operation = SimpleNamespace(
        file_id=uuid4(), tenant_id="north", workspace_id=uuid4(), dataset_id=uuid4(), actor="owner"
    )
    member = SimpleNamespace(table_id=uuid4(), snapshot_id=uuid4(), lineage_run_id=uuid4())
    previous = uuid4()
    state = SimpleNamespace(
        prepared=(member,),
        operation_kind="replace",
        baseline=SimpleNamespace(members=(SimpleNamespace(table_id=member.table_id, snapshot_id=previous),)),
    )
    run = SimpleNamespace(
        id=member.lineage_run_id,
        artifact_id=operation.file_id,
        tenant_id=operation.tenant_id,
        workspace_id=operation.workspace_id,
        dataset_id=operation.dataset_id,
        actor=operation.actor,
        operation="replace",
        predecessor_snapshot_id=previous,
    )
    binding = SimpleNamespace(
        run_id=run.id,
        table_id=member.table_id,
        tenant_id=run.tenant_id,
        workspace_id=run.workspace_id,
        dataset_id=run.dataset_id,
    )
    producer = StructuredSourceProducer.__new__(StructuredSourceProducer)
    producer.operation, producer.runs = operation, {}
    await producer.restore(SimpleNamespace(get=AsyncMock(side_effect=[run, binding])), state)
    assert producer.runs == {str(run.id): member.table_id}


def test_replacement_cannot_run_without_source_producer():
    from koinon.integrations.content_sources.sync_runs import SourceReplacementExecution
    from koinon.knowledge.bulk.structured_pipeline import StructuredBulkPipeline

    execution = SourceReplacementExecution(None, "attempt", str(uuid4()))
    with pytest.raises(ConflictException, match="exact source producer"):
        StructuredBulkPipeline._source_authority(None, None, execution, object())


@pytest.fixture
def replacement_case():
    from flyquery.core.services.ingestion.reader import ProposedTable
    from test_bulk_structured_repository import identity

    from koinon.integrations.content_sources.sync_runs import SourceReplacementExecution
    from koinon.knowledge.bulk.structured_dtos import (
        DatasetReplacementBaseline,
        ReplacementBaselineMember,
        ReplacementMemberPlan,
        SourceReplacementDiscovery,
        SourceReplacementTableEvidence,
        StructuredOperationState,
        StructuredTablePlan,
    )
    from koinon.knowledge.bulk.structured_replacement import discover_members, locator_digest

    original = identity()
    current = identity(
        workspace_id=original.workspace_id,
        dataset_id=original.dataset_id,
        filename="facts.json",
        sha256=hashlib.sha256(b"original").hexdigest(),
    )
    baseline = DatasetReplacementBaseline(
        dataset_id=current.dataset_id,
        catalog_dataset_id=current.catalog_dataset_id,
        source_attempt_id="previous",
        imported_version_id="previous",
        catalog_file_version_id="old-version",
        policy_id="policy",
        local_revision="cpv1:" + "c" * 64,
        source_generation=1,
        policy_revision=1,
        sha256=original.sha256,
        native_file_id=original.file_id,
        members=tuple(
            ReplacementBaselineMember(
                member_key=f'json:["old{i}"]',
                table_id=uuid4(),
                catalog_table_id=f"catalog-{i}",
                snapshot_id=uuid4(),
                source_file_id=original.file_id,
                local_revision="cpv1:" + "c" * 64,
                sha256=original.sha256,
            )
            for i in range(2)
        ),
    )
    members = (
        ReplacementMemberPlan(
            member_key='json:["old1"]',
            action="retain",
            table_id=baseline.members[0].table_id,
            catalog_table_id="catalog-0",
            snapshot_id=uuid4(),
            ordinal=0,
            name="old1",
        ),
        ReplacementMemberPlan(
            member_key='json:["new"]',
            action="add",
            table_id=uuid4(),
            catalog_table_id="catalog-new",
            snapshot_id=uuid4(),
            ordinal=1,
            name="new",
        ),
        ReplacementMemberPlan(
            member_key=baseline.members[1].member_key,
            action="remove",
            table_id=baseline.members[1].table_id,
            catalog_table_id="catalog-1",
            snapshot_id=baseline.members[1].snapshot_id,
        ),
    )
    proposed = (ProposedTable("old1", "old1", 1, 1), ProposedTable("new", "new", 1, 1))
    discovery = SourceReplacementDiscovery(
        file_format="json",
        compression="none",
        content_sha256=current.sha256,
        locator_set_sha256=locator_digest(discover_members("json", proposed)),
        proposed=tuple(
            SourceReplacementTableEvidence(
                name=p.name,
                sheet_or_json_path=p.sheet_or_json_path,
                n_columns=p.n_columns,
                n_rows_estimate=p.n_rows_estimate,
            )
            for p in proposed
        ),
    )
    state = StructuredOperationState(
        identity=current,
        status="admitted",
        operation_kind="replace",
        baseline=baseline,
        baseline_sha256="d" * 64,
        replacement_plan=members,
        plan=tuple(
            StructuredTablePlan(**{key: getattr(m, key) for key in StructuredTablePlan.model_fields})
            for m in members
            if m.action != "remove"
        ),
        source_attempt_id="replacement",
        source_publication_sha256="e" * 64,
    )
    execution = SourceReplacementExecution(
        SimpleNamespace(tenant_id=current.tenant_id, owner=current.actor),
        "replacement",
        str(current.operation_id),
    )
    admission = object()

    @asynccontextmanager
    async def publication():
        yield admission

    producer = SimpleNamespace(
        admission=admission,
        execution=execution,
        operation=current,
        attempt_id="replacement",
        check=lambda: None,
        publication=publication,
        plans=AsyncMock(return_value=state),
        freeze=AsyncMock(),
    )
    return SimpleNamespace(
        identity=current,
        baseline=baseline,
        members=members,
        discovery=discovery,
        proposed=proposed,
        state=state,
        execution=execution,
        admission=admission,
        producer=producer,
    )


@pytest.mark.parametrize("status", ["prepared", "committed"])
async def test_replacement_resume_uses_retained_state_without_bytes_or_processing(
    replacement_case, monkeypatch, status
):
    from koinon.knowledge.bulk import structured_pipeline as module

    case = replacement_case
    state = case.state.model_copy(update={"status": status})

    @asynccontextmanager
    async def write():
        yield SimpleNamespace(get=AsyncMock(return_value=state), _session=object())

    def forbidden(*args, **kwargs):
        pytest.fail("Retained replacement must not open resources or process original bytes")

    pipeline = module.StructuredBulkPipeline(
        SimpleNamespace(write=write, configuration=forbidden), None, None, None, None
    )
    monkeypatch.setattr(module, "run_parse", forbidden)
    monkeypatch.setattr(module, "run_receive", forbidden)
    result = await pipeline.prepare_replacement(
        case.execution,
        case.identity,
        b"",
        source_admission=case.admission,
        source_producer=case.producer,
        baseline=case.baseline,
        baseline_sha256="d" * 64,
        members=case.members,
        discovery_evidence=case.discovery,
    )
    assert result == state


@pytest.mark.parametrize("changed", ["path", "rows", "name", "columns", "compression", "format"])
async def test_discovery_changes_stop_before_native_materialization(
    replacement_case, tmp_path, monkeypatch, changed
):
    from dataclasses import replace

    from koinon.knowledge.bulk import structured_pipeline as module

    case = replacement_case
    materialized = False
    unit = SimpleNamespace(
        get=AsyncMock(return_value=None),
        admit_replacement=AsyncMock(),
        plan_replacement=AsyncMock(return_value=case.state),
        bind_publication=AsyncMock(),
    )

    @asynccontextmanager
    async def write():
        yield unit

    raw = tmp_path / "facts.json"
    raw.write_bytes(b"original")
    received = SimpleNamespace(
        file_id=case.identity.file_id,
        size_bytes=8,
        content_hash_sha256=case.identity.sha256,
        local_temp_path=str(raw),
        file_format="json",
        compression="none",
    )
    proposed = list(case.proposed)
    if changed in {"compression", "format"}:
        setattr(
            received,
            "file_format" if changed == "format" else "compression",
            "jsonl" if changed == "format" else "gzip",
        )
    else:
        field, value = {
            "path": ("sheet_or_json_path", "different"),
            "rows": ("n_rows_estimate", 2),
            "name": ("name", "different"),
            "columns": ("n_columns", 2),
        }[changed]
        proposed[0] = replace(proposed[0], **{field: value})

    async def parse(**values):
        nonlocal materialized
        await values["reserve_tables"](tuple(proposed))
        materialized = True
        raise AssertionError("Changed discovery reached forbidden native materialization")

    monkeypatch.setattr(module, "run_receive", AsyncMock(return_value=received))
    monkeypatch.setattr(module, "run_parse", parse)
    operations = SimpleNamespace(
        configuration=lambda: SimpleNamespace(default_locale="en-US"),
        native=lambda: SimpleNamespace(sessionmaker=object()),
        write=write,
    )
    workspace = SimpleNamespace(
        get=AsyncMock(return_value={"tenant_id": case.identity.tenant_id, "storage_used_bytes": 0}),
        track_storage=AsyncMock(),
    )
    pipeline = module.StructuredBulkPipeline(
        operations, None, SimpleNamespace(get=lambda: object()), SimpleNamespace(get=lambda: workspace), None
    )
    with pytest.raises(ConflictException) as failure:
        await pipeline.prepare_replacement(
            case.execution,
            case.identity,
            b"original",
            source_admission=case.admission,
            source_producer=case.producer,
            baseline=case.baseline,
            baseline_sha256="d" * 64,
            members=case.members,
            discovery_evidence=case.discovery,
        )
    assert failure.value.code == "BULK_NATIVE_RECEIPT_CONFLICT"
    assert not materialized and not raw.exists()


def test_root_discovery_is_stable_across_temporary_filenames():
    from flyquery.core.services.ingestion.reader import ProposedTable

    from koinon.knowledge.bulk.structured_dtos import SourceReplacementDiscovery

    def capture(name, **overrides):
        values = dict(
            filename="facts.csv",
            file_format="csv",
            compression="none",
            content_sha256="a" * 64,
            proposed=(ProposedTable(name, None, 2, 3),),
        )
        return SourceReplacementDiscovery.capture(**{**values, **overrides})

    assert capture("tmp-one") == capture("tmp-two")
    assert capture("tmp-one") != capture("tmp-one", filename="other.csv")
    assert capture("tmp-one") != capture("tmp-one", content_sha256="b" * 64)
    assert capture("tmp-one") != capture("tmp-one", proposed=(ProposedTable("tmp-one", None, 2, 4),))


@pytest.mark.parametrize("changed", ["missing", "admission", "execution", "operation", "attempt"])
async def test_replacement_denies_wrong_source_producer_before_resources(replacement_case, changed):
    from koinon.knowledge.bulk.structured_pipeline import StructuredBulkPipeline

    case = replacement_case
    producer = case.producer
    if changed == "missing":
        producer = None
    elif changed == "attempt":
        producer.attempt_id = "foreign"
    else:
        setattr(producer, changed, object())
    pipeline = StructuredBulkPipeline(None, None, None, None, None)
    with pytest.raises(ConflictException) as failure:
        await pipeline.prepare_replacement(
            case.execution,
            case.identity,
            b"original",
            source_admission=case.admission,
            source_producer=producer,
            baseline=case.baseline,
            baseline_sha256="d" * 64,
            members=case.members,
            discovery_evidence=case.discovery,
        )
    assert failure.value.code == "SOURCE_PUBLICATION_DENIED"


@pytest.mark.parametrize("changed", ["parser", "evidence_bytes", "original_bytes"])
async def test_replacement_rejects_corrupt_discovery_before_resources(replacement_case, changed):
    from koinon.knowledge.bulk.structured_pipeline import StructuredBulkPipeline

    case = replacement_case

    @asynccontextmanager
    async def write():
        yield SimpleNamespace(get=AsyncMock(return_value=None))

    evidence, content = case.discovery, b"original"
    if changed == "parser":
        evidence = evidence.model_copy(update={"parser_fingerprint": "changed-reader"})
    elif changed == "evidence_bytes":
        evidence = evidence.model_copy(update={"content_sha256": "f" * 64})
    else:
        content = b"modified"
    pipeline = StructuredBulkPipeline(SimpleNamespace(write=write), None, None, None, None)
    with pytest.raises(ConflictException) as failure:
        await pipeline.prepare_replacement(
            case.execution,
            case.identity,
            content,
            source_admission=case.admission,
            source_producer=case.producer,
            baseline=case.baseline,
            baseline_sha256="d" * 64,
            members=case.members,
            discovery_evidence=evidence,
        )
    assert failure.value.code == (
        "BULK_NATIVE_RECEIPT_CONFLICT" if changed == "parser" else "BULK_ORIGINAL_INTEGRITY"
    )


@pytest.mark.parametrize("target_kind", ["prior", "next", "foreign", "prior_write"])
async def test_reconcile_guard_only_reads_the_exact_retained_predecessor(
    replacement_case, monkeypatch, target_kind
):
    from flyquery.core.services.ingestion.lineage import StructuredStagePhase, StructuredStageTarget

    from koinon.integrations.content_sources.source_structured import StructuredSourceProducer
    from koinon.knowledge.bulk.structured_repository import StructuredBulkUnit

    case = replacement_case
    producer = StructuredSourceProducer.__new__(StructuredSourceProducer)
    producer.operation = case.identity
    producer.plans = AsyncMock(return_value=case.state)
    snapshot = (
        case.baseline.members[0].snapshot_id
        if target_kind.startswith("prior")
        else case.members[0].snapshot_id
    )
    if target_kind == "foreign":
        snapshot = uuid4()
    session = SimpleNamespace(
        get=AsyncMock(
            return_value=SimpleNamespace(
                tenant_id=case.identity.tenant_id,
                workspace_id=case.identity.workspace_id,
                dataset_id=case.identity.dataset_id,
                table_id=case.members[0].table_id,
                status="READY" if target_kind.startswith("prior") else "PARTIAL",
            )
        )
    )
    monkeypatch.setattr(StructuredBulkUnit, "_replacement_baseline", AsyncMock())
    target = StructuredStageTarget(case.identity.tenant_id, snapshot, table_id=case.members[0].table_id)
    phase = (
        StructuredStagePhase.RECONCILE_WRITE
        if target_kind == "prior_write"
        else StructuredStagePhase.RECONCILE_READ
    )
    if target_kind in {"foreign", "prior_write"}:
        with pytest.raises(ConflictException) as failure:
            await producer.target(session, phase, target)
        assert failure.value.code == "SOURCE_PUBLICATION_DENIED"
    else:
        assert await producer.target(session, phase, target) is None


@pytest.fixture
async def native_replacement(tmp_path, monkeypatch, record_property):
    """Real native schema and stages; the outer primary fence is exercised by source service tests."""
    import os
    from pathlib import Path

    import psycopg
    from alembic import command
    from flyquery.config import FlyquerySettings
    from flyquery.core.eda.ingest_publisher import IngestPublisher
    from flyquery.core.services.ingestion import lineage
    from flyquery.core.services.ingestion.stages import embed
    from flyquery.core.services.storage.adapters.local_fs import LocalFsObjectStore
    from flyquery.core.services.workspaces.workspace_repository import WorkspaceRepository
    from flyquery.core.services.workspaces.workspace_service import WorkspaceService
    from flyquery.data import TenantGucCustomizer
    from flyquery.models.entities.workspace import Workspace
    from psycopg import sql
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from test_bulk_pinned_postgres import load
    from test_bulk_structured_repository import identity

    from koinon.knowledge.adapters import native_scope
    from koinon.knowledge.bulk.dtos import BulkDestination
    from koinon.knowledge.bulk.queue import BulkLease
    from koinon.knowledge.bulk.structured_pipeline import StructuredBulkPipeline
    from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository
    from koinon.knowledge.lineage.service import NativeStructuredLineage

    uri = os.environ.get("KOINON_CONTENT_SOURCES_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires the explicitly owned source PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port == 55439
    database = "replacement_native_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database))
        )
    record_property("owned_database", database)
    url = base.set(database=database)
    root = Path(__file__).resolve().parents[4]
    migrate = load(root / "deploy/migrate.py", "replacement_native_migrate")
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as connection:
            config = migrate.history_config(
                "structured", root / "packages/structured/migrations/versions", connection
            )
            command.upgrade(config, "head")
            connection.commit()
    finally:
        engine.dispose()
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
                            "datasources": {
                                "structured": {
                                    "url": url.set(drivername="postgresql+asyncpg").render_as_string(
                                        hide_password=False
                                    ),
                                    "ddl-auto": "none",
                                }
                            },
                        }
                    }
                }
            }
        )
    )
    context.register_bean(StructuredBulkRepository)
    await context.start()
    try:
        registry = context.get_bean(DataSourceRegistry)
        native = registry.get("structured")
        registry.add_customizer(TenantGucCustomizer(native.name), datasource=native.name)
        settings = FlyquerySettings(pii_scanner="disabled")
        settings.bind_native_resources(None, registry)
        repository = context.get_bean(StructuredBulkRepository)
        repository.settings = SimpleNamespace(get=lambda: settings)
        original = b'{"old0":[{"common":1,"obsolete":2}],"old1":[{"x":3}]}'
        owned = identity(
            filename="facts.json", sha256=hashlib.sha256(original).hexdigest(), size_bytes=len(original)
        )
        lease = BulkLease(
            job_id="job",
            item_id=str(owned.operation_id),
            batch_id="batch",
            tenant_id=owned.tenant_id,
            subject=owned.actor,
            token_id=None,
            worker_id="worker",
            attempt=1,
            source_id=owned.catalog_source_id,
            asset_id=owned.catalog_dataset_id,
            filename=owned.filename,
            size_bytes=len(original),
            sha256=owned.sha256,
            mode="dataset",
            destination=BulkDestination(workspace_id="workspace", project_id="project", parent_id="parent"),
        )

        @asynccontextmanager
        async def publication(*args):
            yield None

        queue = SimpleNamespace(
            check=AsyncMock(),
            _check=AsyncMock(),
            publication=publication,
            reserve_tables=AsyncMock(
                side_effect=lambda _, plans: tuple(
                    p.model_copy(update={"catalog_table_id": f"catalog-{p.ordinal}"}) for p in plans
                )
            ),
        )
        model_calls = []

        class Embedder:
            model = "controlled:native-replacement-test"

            async def embed_batch(self, texts):
                model_calls.append(tuple(texts))
                return [[1.0] * 1536 for _ in texts]

        monkeypatch.setattr(embed, "build_embedder", lambda settings: Embedder())
        pipeline = StructuredBulkPipeline(
            repository,
            queue,
            SimpleNamespace(get=lambda: LocalFsObjectStore(str(tmp_path / "artifacts"))),
            SimpleNamespace(get=lambda: WorkspaceService(WorkspaceRepository(native.sessionmaker))),
            SimpleNamespace(get=lambda: IngestPublisher(None)),
        )
        owner = NativeStructuredLineage(registry)
        with native_scope("structured", owned.tenant_id, str(owned.workspace_id), owned.actor):
            async with infrastructure_unit(native) as session:
                session.add(
                    Workspace(id=owned.workspace_id, tenant_id=owned.tenant_id, slug="source", name="Source")
                )
            sink = owner.sink(
                actor=owned.actor,
                tenant_id=owned.tenant_id,
                workspace_id=owned.workspace_id,
                dataset_id=owned.dataset_id,
                operation="upload",
                authorize=AsyncMock(),
            )
            with lineage.observe(sink):
                await pipeline.prepare(lease, owned, original)
                initial = await pipeline.finalize(lease, owned)
            yield SimpleNamespace(
                repository=repository,
                pipeline=pipeline,
                initial=initial,
                owner=owner,
                native=native,
                model_calls=model_calls,
                settings=settings,
            )
    finally:
        await context.stop()


@pytest.mark.integration
@pytest.mark.parametrize("failure", [None, "deferred", "second_publish"])
async def test_native_replacement_prepare_and_publish_are_atomic_and_restartable(
    native_replacement, monkeypatch, failure
):
    import json

    from flyquery.core.services.ingestion.reader import ProposedTable
    from flyquery.models.entities.schema import SchemaChange, SchemaObject, SchemaSnapshot
    from flyquery.models.entities.table import Table
    from sqlalchemy import select, text

    from koinon.integrations.content_sources.source_structured import StructuredSourceProducer
    from koinon.integrations.content_sources.sync_runs import SourceReplacementExecution
    from koinon.knowledge.bulk import structured_pipeline as module
    from koinon.knowledge.bulk.ports import SourcePublicationBinding
    from koinon.knowledge.bulk.structured_dtos import (
        DatasetReplacementBaseline,
        ReplacementBaselineMember,
        ReplacementMemberPlan,
        SourceReplacementDiscovery,
    )

    case = native_replacement
    old = case.initial
    content = b'{"old1":[{"common":4}],"new":[{"x":5}]}'
    identity = old.identity.model_copy(
        update={
            "operation_id": uuid4(),
            "file_id": uuid4(),
            "catalog_file_version_id": "replacement-version",
            "sha256": hashlib.sha256(content).hexdigest(),
            "size_bytes": len(content),
        }
    )
    baseline = DatasetReplacementBaseline(
        dataset_id=identity.dataset_id,
        catalog_dataset_id=identity.catalog_dataset_id,
        source_attempt_id="previous",
        imported_version_id="previous",
        catalog_file_version_id=old.identity.catalog_file_version_id,
        policy_id="policy",
        local_revision="cpv1:" + "c" * 64,
        source_generation=1,
        policy_revision=1,
        sha256=old.identity.sha256,
        native_file_id=old.identity.file_id,
        members=tuple(
            ReplacementBaselineMember(
                member_key=p.member_key,
                table_id=p.table_id,
                catalog_table_id=p.catalog_table_id,
                snapshot_id=p.snapshot_id,
                source_file_id=old.identity.file_id,
                local_revision="cpv1:" + "c" * 64,
                sha256=old.identity.sha256,
            )
            for p in old.prepared
        ),
    )
    members = (
        ReplacementMemberPlan(
            member_key='json:["old1"]',
            action="retain",
            table_id=old.prepared[0].table_id,
            catalog_table_id=old.prepared[0].catalog_table_id,
            snapshot_id=uuid4(),
            ordinal=0,
            name="old1",
        ),
        ReplacementMemberPlan(
            member_key='json:["new"]',
            action="add",
            table_id=uuid4(),
            catalog_table_id="catalog-new",
            snapshot_id=uuid4(),
            ordinal=1,
            name="new",
        ),
        ReplacementMemberPlan(
            member_key=old.prepared[1].member_key,
            action="remove",
            table_id=old.prepared[1].table_id,
            catalog_table_id=old.prepared[1].catalog_table_id,
            snapshot_id=old.prepared[1].snapshot_id,
        ),
    )
    evidence = SourceReplacementDiscovery.capture(
        filename=identity.filename,
        file_format="json",
        compression="none",
        content_sha256=identity.sha256,
        proposed=(ProposedTable("old1", "old1", 0, 1), ProposedTable("new", "new", 0, 1)),
    )
    async with case.repository.read() as unit:
        baseline_sha256 = await unit._session.scalar(
            text("SELECT public.koinon_json_sha256(CAST(:payload AS jsonb))"),
            {"payload": json.dumps(baseline.model_dump(mode="json", by_alias=True))},
        )
    admission = object()
    execution = SourceReplacementExecution(
        SimpleNamespace(tenant_id=identity.tenant_id, owner=identity.actor),
        "replacement",
        str(identity.operation_id),
    )

    @asynccontextmanager
    async def publication():
        yield admission

    class NativeProducer(StructuredSourceProducer):
        """Keep the real native guard; the primary contract is covered by service integration tests."""

        def held_admission(self):
            self.check()
            return admission

        @asynccontextmanager
        async def local(self):
            self.check()
            async with self.native() as session:
                yield session

        async def freeze(self, current, plans):
            assert current is admission and plans == members
            return SourcePublicationBinding("replacement", "e" * 64)

        async def plans(self, session):
            from koinon.knowledge.bulk.structured_repository import StructuredBulkUnit

            state = await StructuredBulkUnit(session).get(identity)
            assert state.source_attempt_id == "replacement" and state.source_publication_sha256 == "e" * 64
            return state

    def producer():
        return NativeProducer(None, admission, execution, identity, publication, case.owner, "replacement")

    async def state():
        async with case.repository.read() as unit:
            tables = (
                await unit._session.scalars(
                    select(Table).where(Table.dataset_id == identity.dataset_id).order_by(Table.id)
                )
            ).all()
            return {
                t.id: (t.name, t.current_snapshot_id, t.source_file_id, t.is_active, t.archived_at)
                for t in tables
            }

    previous = await state()
    prepared = await case.pipeline.prepare_replacement(
        execution,
        identity,
        content,
        source_admission=admission,
        source_producer=producer(),
        baseline=baseline,
        baseline_sha256=baseline_sha256,
        members=members,
        discovery_evidence=evidence,
    )
    assert prepared.status == "prepared" and prepared.prepared[0].reconcile_changes.removed_object_ids
    staged = await state()
    assert all(staged[key] == value for key, value in previous.items())
    assert staged[members[1].table_id][1] is None and not staged[members[1].table_id][3]
    calls = len(case.model_calls)

    async def forbidden(*args, **kwargs):
        pytest.fail("Prepared or committed recovery must not parse, receive or call a model")

    monkeypatch.setattr(module, "run_parse", forbidden)
    monkeypatch.setattr(module, "run_receive", forbidden)
    resumed = await case.pipeline.prepare_replacement(
        execution,
        identity,
        b"",
        source_admission=admission,
        source_producer=producer(),
        baseline=baseline,
        baseline_sha256=baseline_sha256,
        members=members,
        discovery_evidence=evidence,
    )
    assert resumed == prepared and len(case.model_calls) == calls
    original_deferred, original_publish = module.publish_reconcile_changes, module.run_publish
    published = 0

    async def deferred(session, changes):
        await original_deferred(session, changes)
        if failure == "deferred":
            raise RuntimeError("after deferred changes")

    async def publish(**values):
        nonlocal published
        await original_publish(**values)
        published += 1
        if failure == "second_publish" and published == 2:
            raise RuntimeError("after second publish")

    monkeypatch.setattr(module, "publish_reconcile_changes", deferred)
    monkeypatch.setattr(module, "run_publish", publish)
    if failure:
        with pytest.raises(RuntimeError):
            await case.pipeline.finalize_replacement(
                execution, identity, source_admission=admission, source_producer=producer()
            )
        assert await state() == staged
        async with case.repository.read() as unit:
            assert (await unit.get(identity)).status == "prepared"
            for identifier in prepared.prepared[0].reconcile_changes.removed_object_ids:
                assert (await unit._session.get(SchemaObject, identifier)).is_active
            assert not (
                await unit._session.scalars(
                    select(SchemaChange).where(SchemaChange.next_snapshot_id == members[0].snapshot_id)
                )
            ).all()
        monkeypatch.setattr(module, "publish_reconcile_changes", original_deferred)
        monkeypatch.setattr(module, "run_publish", original_publish)
    committed = await case.pipeline.finalize_replacement(
        execution, identity, source_admission=admission, source_producer=producer()
    )
    assert committed.status == "committed" and committed.receipt.tables == prepared.prepared
    final = await state()
    assert final[members[0].table_id][:4] == ("old1", members[0].snapshot_id, identity.file_id, True)
    assert final[members[1].table_id][:4] == ("new", members[1].snapshot_id, identity.file_id, True)
    assert final[members[2].table_id][1:4] == (members[2].snapshot_id, old.identity.file_id, False)
    async with case.repository.read() as unit:
        for table in prepared.prepared:
            assert (await unit._session.get(SchemaSnapshot, table.snapshot_id)).status == "READY"
        for identifier in prepared.prepared[0].reconcile_changes.removed_object_ids:
            assert not (await unit._session.get(SchemaObject, identifier)).is_active
    replay = await case.pipeline.finalize_replacement(
        execution, identity, source_admission=admission, source_producer=producer()
    )
    assert replay == committed and len(case.model_calls) == calls
