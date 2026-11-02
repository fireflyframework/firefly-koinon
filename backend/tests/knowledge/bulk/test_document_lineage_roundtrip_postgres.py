# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Observe a real native admission through the same role-scoped bulk receipt adapter."""

import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from psycopg import sql
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from test_bulk_native import bulk as bulk
from test_bulk_pinned_postgres import load
from test_bulk_processing_recovery import failed_before_native
from test_bulk_processing_recovery_postgres import native_reader

pytestmark = pytest.mark.integration


@pytest.fixture
def bulk_url(monkeypatch):
    monkeypatch.setenv("PYFLY_DATA_RELATIONAL_POOL_SIZE", "2")
    monkeypatch.setenv("PYFLY_DATA_RELATIONAL_POOL_MAX_OVERFLOW", "0")
    monkeypatch.setenv("PYFLY_DATA_RELATIONAL_POOL_TIMEOUT", "2")
    uri = os.environ.get("KOINON_TEST_BULK_POSTGRES_URL")
    if not uri:
        pytest.skip("Requires a clearly owned PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port != 18783
    database = "document_roundtrip_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database))
        )
    url = base.set(database=database)
    root = Path(__file__).parents[4]
    migrate = load(root / "deploy/migrate.py", "document_roundtrip_migrate")
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as connection:
            config = migrate.history_config("native", root / "deploy/migrations/native_versions", connection)
            command.upgrade(config, "heads")
            connection.commit()
    finally:
        engine.dispose()
    return url.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)


async def test_native_lineage_admission_roundtrips_through_bulk_inspection(bulk, bulk_url, tmp_path):
    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.data import TenantGucCustomizer
    from flycanon.models.repositories.source_repository import SourceRepository

    from koinon.knowledge.adapters import native_scope

    batch_id, item_id, lease, _ = await failed_before_native(bulk)
    port = await native_reader(bulk, bulk_url)
    registry = bulk.context.get_bean(DataSourceRegistry)
    writer = registry.register("canon_roundtrip_writer", bulk_url)
    registry.add_customizer(TenantGucCustomizer(writer.name), datasource=writer.name)
    lineage = DocumentLineage(
        SourceRepository(writer.sessionmaker, engine=writer.engine),
        LocalFsObjectStore(str(tmp_path / "originals")),
    )
    scope = DocumentScope(lease.tenant_id, bulk.target["workspace_id"], lease.subject)
    with native_scope("canon", scope.tenant_id, scope.workspace_id, scope.actor):
        admitted = await lineage.admit(
            scope,
            logical_key=lease.source_id,
            operation_id="upload:" + lease.source_id,
            content=b"original",
            filename=lease.filename,
            media_type="text/plain",
        )
    assert admitted.sha256 == lease.sha256 and admitted.bytes == lease.size_bytes
    observation = await port.inspect(lease)
    assert observation.status == "admitted" and observation.receipt is None
    current = await bulk.service.processing_recovery(lease.subject, lease.tenant_id, batch_id, item_id)
    assert current.native_state == "admitted" and current.operation is None


@pytest.mark.parametrize(
    "canon_pool_size,outcome",
    [
        (1, "success"),
        (2, "success"),
        (1, "revoked"),
        (2, "revoked"),
        (1, "rollback"),
        (2, "rollback"),
        (1, "concurrent"),
    ],
)
async def test_actual_native_transform_promotes_and_bulk_receipt_is_recoverable(
    bulk, bulk_url, tmp_path, canon_pool_size, outcome
):
    import asyncio
    from dataclasses import replace
    from types import SimpleNamespace

    from flycanon.config import CanonSettings
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetService
    from flycanon.core.services.ingestion.chunker import ParagraphChunker
    from flycanon.core.services.ingestion.ingestion_service import IngestionService
    from flycanon.core.services.ingestion.loaders import default_registry
    from flycanon.core.services.sources.intake_runtime import build_intake_components
    from flycanon.core.services.sources.lineage.pipeline import DocumentLineagePipeline
    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.data import TenantGucCustomizer
    from flycanon.interfaces.dtos.source import SubmitSourceRequest
    from flycanon.interfaces.enums import SourceKind
    from flycanon.models.entities.embedding_set import EmbeddingSetRow
    from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
    from flycanon.models.entities.workspace import Workspace
    from flycanon.models.repositories.chunk_repository import ChunkRepository
    from flycanon.models.repositories.embedding_set_repository import EmbeddingSetRepository
    from flycanon.models.repositories.source_repository import SourceRepository
    from pyfly.data.transaction import infrastructure_unit
    from test_bulk_queue import queued

    from koinon.knowledge.adapters import native_scope
    from koinon.knowledge.bulk.queue import BulkQueue

    await queued(bulk, "transform")
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("native-transform")
    port = await native_reader(bulk, bulk_url)
    await port.reserve(lease)
    registry = bulk.context.get_bean(DataSourceRegistry)
    properties = registry.properties.derived(bulk_url)
    properties = replace(
        properties, pool=replace(properties.pool, size=canon_pool_size, max_overflow=0, timeout=2)
    )
    writer = registry.register("canon_transform_writer", bulk_url, properties=properties)
    assert writer.engine.pool.size() == canon_pool_size
    assert registry.primary.engine.pool.size() == 2
    registry.add_customizer(TenantGucCustomizer(writer.name), datasource=writer.name)
    async with writer.engine.begin() as connection:
        for entity in (Workspace, EmbeddingSetRow, KnowledgeChunkRow):
            await connection.run_sync(lambda sync, entity=entity: entity.__table__.create(sync))
    stages = []
    revocations = []

    async def revoke_concurrently():
        import contextvars

        from pyfly.data.transaction import TransactionTemplate
        from sqlalchemy import delete, text

        from koinon.catalog.entities import Membership

        pid_ready = asyncio.get_running_loop().create_future()

        async def revoke():
            async with TransactionTemplate(registry.primary).transaction() as unit:
                pid_ready.set_result(await unit.resource.scalar(text("SELECT pg_backend_pid()")))
                await unit.resource.execute(delete(Membership).where(Membership.id == "editor"))

        task = asyncio.create_task(revoke(), context=contextvars.Context())
        revocations.append(task)
        pid = await asyncio.wait_for(pid_ready, 2)

        def waiting():
            with psycopg.connect(
                make_url(bulk_url).set(drivername="postgresql").render_as_string(hide_password=False)
            ) as connection:
                return connection.execute(
                    "SELECT wait_event_type='Lock' FROM pg_stat_activity WHERE pid=%s", (pid,)
                ).fetchone()[0]

        async with asyncio.timeout(3):
            while not await asyncio.to_thread(waiting):
                assert not task.done()
                await asyncio.sleep(0.01)
        assert not task.done()

    class Embedder:
        model = "controlled:unit"

        async def embed(self, texts):
            stages.append("embed")
            if outcome == "revoked":
                from koinon.catalog.repositories import MembershipRepository

                await bulk.context.get_bean(MembershipRepository).delete_by_id("editor")
            return [[1.0] * 64 for _ in texts]

    class Registry:
        def for_binding(self, binding):
            assert binding.set_id == "active-set"
            return Embedder()

    class Index:
        async def replace_for_source(self, **kwargs):
            stages.append("index")
            if outcome == "concurrent":
                await revoke_concurrently()
            if outcome == "rollback":
                raise RuntimeError("controlled native index failure")
            return len(kwargs["chunks"])

    class Audit:
        async def record(self, **kwargs):
            stages.append("audit")

    async def processing():
        stages.append("processing")
        await queue.check(lease)

    sources = SourceRepository(writer.sessionmaker, engine=writer.engine)
    lineage = DocumentLineage(sources, LocalFsObjectStore(str(tmp_path / "originals")))
    loaders = default_registry()
    settings = CanonSettings(store_originals=True, pii_policy="disabled")
    components = build_intake_components(
        binary_normalizer=None,
        ingestion=IngestionService(loaders=loaders, chunker=ParagraphChunker()),
        loaders=loaders,
        embeddings=Embedder(),
        indexer=Index(),
        metadata_extractor=SimpleNamespace(extract=lambda *a, **kw: None),
        source_repository=sources,
        chunk_repository=ChunkRepository(writer.sessionmaker, engine=writer.engine),
        audit=Audit(),
        event_publisher=None,
        object_store=lineage.store,
        settings=settings,
        embedding_sets=EmbeddingSetService(
            repository=EmbeddingSetRepository(writer.sessionmaker, engine=writer.engine), settings=settings
        ),
        embedding_registry=Registry(),
    )
    pipeline = DocumentLineagePipeline(components, lineage)
    with native_scope("canon", lease.tenant_id, bulk.target["workspace_id"], lease.subject):
        async with infrastructure_unit(writer) as session:
            session.add(
                Workspace(
                    id=bulk.target["workspace_id"],
                    tenant_id=lease.tenant_id,
                    name="Native",
                    active_embedding_set_id="active-set",
                )
            )
            session.add(
                EmbeddingSetRow(
                    id="active-set",
                    tenant_id=lease.tenant_id,
                    workspace_id=bulk.target["workspace_id"],
                    provider="controlled",
                    model="unit",
                    dimensions=64,
                    status="active",
                    config_fingerprint="0" * 64,
                )
            )
        operation = pipeline.run(
            request=SubmitSourceRequest(kind=SourceKind.text),
            content=b"original",
            tenant_id=lease.tenant_id,
            workspace_id=bulk.target["workspace_id"],
            actor=lease.subject,
            filename=lease.filename,
            content_type="text/plain",
            logical_key=lease.source_id,
            operation_id="upload:" + lease.source_id,
            validate_processing=processing,
            publication_guard=lambda: queue.publication(lease),
            validate_publication=lambda: queue._check(lease),
            prepared_document=SimpleNamespace(
                text="original", sections=[{"path": [], "body": "original"}], metadata={}
            ),
        )
        if outcome in {"revoked", "rollback"}:
            from pyfly.kernel import ForbiddenException

            expected = ForbiddenException if outcome == "revoked" else RuntimeError
            with pytest.raises(expected):
                await asyncio.wait_for(operation, 10)
            observation = await port.inspect(lease) if outcome == "rollback" else None
            if observation is not None:
                assert observation.status == "admitted" and observation.receipt is None
            from flycanon.core.services.sources.lineage.dtos import DocumentScope
            from flycanon.core.services.sources.lineage.ports import LineageQuery

            scope = DocumentScope(lease.tenant_id, bulk.target["workspace_id"], lease.subject)
            async with lineage.repository.read() as unit:
                assert await unit.count(LineageQuery("extraction", scope)) == 0
                assert await unit.count(LineageQuery("version", scope)) == 1
            assert "audit" not in stages
            if outcome == "revoked":
                assert "index" not in stages
            return
        row = await asyncio.wait_for(operation, 10)
    for revocation in revocations:
        await asyncio.wait_for(revocation, 3)
    if outcome == "concurrent":
        from pyfly.kernel import ForbiddenException

        with pytest.raises(ForbiddenException):
            await queue.check(lease)
    assert row.n_chunks == 1
    assert stages == ["processing", "processing", "processing", "embed", "processing", "index", "audit"]
    observation = await port.inspect(lease)
    assert observation.status == "committed"
    assert observation.receipt is not None
    assert observation.receipt.native_source_id == row.id
