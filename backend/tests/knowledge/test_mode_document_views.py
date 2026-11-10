# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from flycanon.config import CanonSettings
from flycanon.core.services.ingestion.chunker import ParagraphChunker
from flycanon.core.services.ingestion.ingestion_service import IngestionService
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.sources.intake_runtime import build_intake_components
from flycanon.core.services.sources.intake_service import IntakeService
from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.core.services.sources.lineage.pipeline import DocumentLineagePipeline
from flycanon.core.services.sources.lineage.service import DocumentLineage
from flycanon.core.services.storage.local_fs import LocalFsObjectStore
from flycanon.interfaces.dtos.source import SubmitSourceRequest
from flycanon.models.entities import Base
from flycanon.models.entities.source_lineage import metadata, source_artifacts
from flycanon.models.repositories.chunk_repository import ChunkRepository
from flycanon.models.repositories.source_repository import SourceRepository
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def recorded(tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(metadata.create_all)
        await connection.execute(text("DROP INDEX uq_canon_sources_tenant_workspace_content_sha256"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sources = SourceRepository(sessions, engine=engine)
    store = LocalFsObjectStore(str(tmp_path / "objects"))
    lineage = DocumentLineage(sources, store)
    embed = AsyncMock(side_effect=lambda texts: [[1.0] for _ in texts])
    index = AsyncMock(return_value=1)
    loaders = default_registry()
    dependencies = dict(
        binary_normalizer=None,
        ingestion=IngestionService(loaders=loaders, chunker=ParagraphChunker()),
        loaders=loaders,
        embeddings=SimpleNamespace(model="controlled", embed=embed),
        indexer=SimpleNamespace(replace_for_source=index),
        metadata_extractor=SimpleNamespace(extract=Mock(return_value=SimpleNamespace(to_dict=lambda: {}))),
        source_repository=sources,
        chunk_repository=ChunkRepository(sessions, engine=engine),
        audit=SimpleNamespace(record=AsyncMock()),
        event_publisher=None,
        object_store=store,
        settings=CanonSettings(store_originals=True, pii_policy="disabled"),
    )
    pipeline = DocumentLineagePipeline(build_intake_components(**dependencies), lineage)
    intake = IntakeService(
        **dependencies, lineage_pipeline=pipeline, intake_policy=pipeline.components.policy
    )
    path = tmp_path / "source.txt"
    path.write_bytes(b"North revenue is 125.\n")
    source = await intake.submit_file(
        path=path,
        original_reference=None,
        request=SubmitSourceRequest(),
        tenant_id="north",
        workspace_id="native-workspace",
        actor="issuer|admin",
        filename="source.txt",
        content_type="text/plain",
        logical_source_key="source-parent",
        operation_id="initial-upload",
    )
    resolved = {SourceRepository: sources, DocumentLineage: lineage}
    domains = SimpleNamespace(_resolve=lambda kind: resolved[kind])
    try:
        yield SimpleNamespace(
            source=source, lineage=lineage, domains=domains, embed=embed, index=index, store=store
        )
    finally:
        await engine.dispose()


async def prepare(recorded, authorize=None, publication_guard=None):
    service = import_module("koinon.organization_knowledge.transitions.document_views").ModeDocumentViews(
        recorded.domains
    )
    return await service.prepare(
        tenant_id="north",
        workspace_id="native-workspace",
        source_id=recorded.source.id,
        actor="issuer|admin",
        authorize=authorize or AsyncMock(),
        publication_guard=publication_guard,
    )


async def test_actual_recorded_view_creation_and_reuse_never_embed_or_change_ingestion_head(recorded):
    scope = DocumentScope("north", "native-workspace", "issuer|admin")
    before = dict(await recorded.lineage.head(scope, recorded.source.id))
    baseline = (recorded.embed.await_count, recorded.index.await_count)
    first = await prepare(recorded)
    second = await prepare(recorded)
    assert first == second
    assert first["source_version_id"] == before["version_id"]
    assert first["ingestion_extraction_id"] == before["extraction_id"]
    assert first["view_extraction_id"] != before["extraction_id"]
    assert first["text_bytes"] > 0 and first["parts"] == 1
    assert (recorded.embed.await_count, recorded.index.await_count) == baseline
    assert dict(await recorded.lineage.head(scope, recorded.source.id)) == before


async def test_view_preparation_rechecks_permission_before_releasing_ready_receipt(recorded):
    callback = AsyncMock(side_effect=[None, PermissionError("revoked")])
    with pytest.raises(PermissionError):
        await prepare(recorded, callback)


async def test_corrupted_original_never_becomes_a_ready_view(recorded):
    async with recorded.lineage.sources.session() as session:
        key = await session.scalar(
            select(source_artifacts.c.object_key).where(
                source_artifacts.c.source_id == recorded.source.id, source_artifacts.c.role == "raw"
            )
        )
    await recorded.store.put(key, b"changed")
    with pytest.raises(ServiceUnavailableException):
        await prepare(recorded)


async def test_whole_view_guard_precedes_native_write_and_excludes_blob_io(recorded, monkeypatch):
    events, held, writing = [], [], []
    original_write = recorded.lineage.repository.write
    original_put = recorded.store.put

    @asynccontextmanager
    async def guard():
        events.append("guard")
        held.append(True)
        try:
            yield
        finally:
            held.pop()
            events.append("released")

    @asynccontextmanager
    async def write():
        assert held
        events.append("native_write")
        writing.append(True)
        try:
            async with original_write() as unit:
                yield unit
        finally:
            writing.pop()

    async def put(*args, **kwargs):
        assert not held
        events.append("blob")
        return await original_put(*args, **kwargs)

    async def authorize():
        assert not writing

    monkeypatch.setattr(recorded.lineage.repository, "write", write)
    monkeypatch.setattr(recorded.store, "put", put)
    await prepare(recorded, authorize, guard)
    assert events == ["blob", "guard", "native_write", "released"]


async def test_legacy_source_without_committed_head_has_an_exact_reprocessing_prerequisite(recorded):
    from flycanon.models.entities.source_lineage import source_heads
    from sqlalchemy import delete

    async with recorded.lineage.sources.session() as session:
        await session.execute(delete(source_heads).where(source_heads.c.source_id == recorded.source.id))
    before = (recorded.embed.await_count, recorded.index.await_count)
    with pytest.raises(ServiceUnavailableException) as error:
        await prepare(recorded)
    assert error.value.code == "SOURCE_VERSION_PREPARATION_REQUIRED"
    assert (recorded.embed.await_count, recorded.index.await_count) == before


async def test_changed_committed_head_is_rejected_before_ready_receipt(recorded):
    from flycanon.core.services.sources.lineage.ports import LineageQuery
    from pyfly.kernel import ConflictException

    calls = 0

    async def authorize():
        nonlocal calls
        calls += 1
        if calls == 2:
            scope = DocumentScope("north", "native-workspace", "issuer|admin")
            async with recorded.lineage.repository.write() as unit:
                await unit.update(
                    LineageQuery("head", scope, source_id=recorded.source.id), {"extraction_id": None}
                )

    with pytest.raises(ConflictException) as error:
        await prepare(recorded, authorize)
    assert error.value.code == "DOCUMENT_VERSION_CONFLICT"


async def test_activation_receipts_recheck_exact_current_native_pins(recorded):
    from pyfly.kernel import ConflictException

    receipt = await prepare(recorded)
    service = import_module("koinon.organization_knowledge.transitions.document_views").ModeDocumentViews(
        recorded.domains
    )
    options = dict(tenant_id="north", workspace_id="native-workspace", actor="issuer|admin")
    await service.verify_pins(**options, pins=[{"source_id": recorded.source.id, **receipt}])
    with pytest.raises(ConflictException):
        await service.verify_pins(**options, pins=[{"source_id": "foreign-source", **receipt}])
    with pytest.raises(ConflictException):
        await service.verify_pins(
            **options,
            pins=[
                {
                    "source_id": recorded.source.id,
                    **receipt,
                    "view_extraction_id": receipt["ingestion_extraction_id"],
                }
            ],
        )
    with pytest.raises(ValueError):
        await service.verify_pins(**options, pins=[{"source_id": recorded.source.id, **receipt}] * 201)


async def test_source_readiness_requires_exact_scope_and_processed_status(recorded):
    from pyfly.kernel import ConflictException

    service = import_module("koinon.organization_knowledge.transitions.document_views").ModeDocumentViews(
        recorded.domains
    )
    options = dict(tenant_id="north", workspace_id="native-workspace", actor="issuer|admin")
    await service.verify_sources(**options, source_ids=[recorded.source.id])
    with pytest.raises(ConflictException):
        await service.verify_sources(
            **{**options, "workspace_id": "foreign-workspace"}, source_ids=[recorded.source.id]
        )
    repository = recorded.domains._resolve(SourceRepository)
    source = await repository.get(recorded.source.id, tenant_id="north", workspace_id="native-workspace")
    source.status = "failed"
    await repository.update(source)
    with pytest.raises(ConflictException) as error:
        await service.verify_sources(**options, source_ids=[recorded.source.id])
    assert error.value.code == "SOURCE_PROCESSING_REQUIRED"
