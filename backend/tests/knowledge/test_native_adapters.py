# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def configured_connections(container, embeddings=None):
    from contextlib import asynccontextmanager

    from koinon.knowledge.model_bindings import DomainConnections, KnowledgeConnectionResolver

    @asynccontextmanager
    async def resolve(**scope):
        yield DomainConnections({}, embeddings or {})

    resolver = SimpleNamespace(resolve=resolve)
    contains, previous = container.contains_type, container.resolve
    container.contains_type = lambda kind: kind is KnowledgeConnectionResolver or contains(kind)
    container.resolve = lambda kind: resolver if kind is KnowledgeConnectionResolver else previous(kind)
    return container


async def test_document_adapter_runs_retained_normalize_load_chunk_embed_index_and_persistence(tmp_path):
    """Only the provider and external index infrastructure are controlled test seams."""
    from flycanon.config import CanonSettings
    from flycanon.core.agents.model_bindings import EmbeddingBinding
    from flycanon.core.services.audit.audit_service import AuditService
    from flycanon.core.services.embeddings.embedding_service import EmbeddingService
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetBinding, bind_embedding_set
    from flycanon.core.services.ingestion.chunker import ParagraphChunker
    from flycanon.core.services.ingestion.ingestion_service import IngestionService
    from flycanon.core.services.ingestion.loaders import default_registry
    from flycanon.core.services.metadata.extractor import MetadataExtractor
    from flycanon.core.services.retrieval.corpus_factory import CorpusContext
    from flycanon.core.services.retrieval.index_service import IndexService
    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.models.entities import Base
    from flycanon.models.entities.source_lineage import metadata as lineage_metadata
    from flycanon.models.repositories import AuditRepository, ChunkRepository, SourceRepository
    from pyfly.agentic.content.binary import BinaryConfig, BinaryNormalizer
    from pyfly.agentic.embeddings import BaseEmbedder
    from pyfly.agentic.vectorstores import InMemoryVectorStore, TenantScopedVectorStore
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.knowledge.adapters import NativeDomains

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'canon.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(lineage_metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sources, chunks = SourceRepository(sessions, engine=engine), ChunkRepository(sessions, engine=engine)
    audits = AuditRepository(sessions, engine=engine)
    settings = CanonSettings(pii_policy="disabled")
    loaders = default_registry()
    vectors = TenantScopedVectorStore(InMemoryVectorStore())
    lexical = SimpleNamespace(delete_by_doc_id=AsyncMock(), upsert_chunks=AsyncMock())
    context = CorpusContext(corpus=lexical, vector_store=vectors, backend="explicit-test-memory")
    embedder = SimpleNamespace(
        embed=AsyncMock(side_effect=lambda texts: SimpleNamespace(embeddings=[[0.1] * 128 for _ in texts]))
    )

    class Controlled(BaseEmbedder):
        async def _embed_batch(self, texts, **kwargs):
            return (await embedder.embed(texts)).embeddings

    selected = Controlled(model="controlled", dimensions=128)
    objects = LocalFsObjectStore(str(tmp_path / "objects"))
    intake = _versioned_intake(
        dict(
            binary_normalizer=BinaryNormalizer(config=BinaryConfig(max_bytes=1024)),
            ingestion=IngestionService(loaders=loaders, chunker=ParagraphChunker(128, 16)),
            loaders=loaders,
            embeddings=EmbeddingService(embedder=embedder, model="test:controlled", dimensions=128),
            indexer=IndexService(context=context, chunk_repository=chunks),
            metadata_extractor=MetadataExtractor(),
            source_repository=sources,
            chunk_repository=chunks,
            audit=AuditService(repository=audits, event_publisher=None, settings=settings),
            event_publisher=SimpleNamespace(publish=AsyncMock()),
            object_store=objects,
            settings=settings,
        )
    )
    container = SimpleNamespace(
        contains_type=lambda cls: cls is IntakeService,
        resolve=lambda cls: intake,
        registered_types=lambda: [],
    )
    configured_connections(
        container,
        {"documents.embedding": EmbeddingBinding(selected, "test:controlled", 128, 128, "controlled-set")},
    )
    try:
        with bind_embedding_set(EmbeddingSetBinding("controlled-set", "test", "controlled", 128)):
            result = await NativeDomains(container).ingest_document(
                tenant_id="north",
                workspace_id="workspace",
                filename="evidence.md",
                content=b"# Scope\n\nThe acceptance threshold is twelve documents.",
                actor="issuer|alice",
                source_catalog_id="catalog-source",
            )
        row = await sources.get(result["source_id"], tenant_id="north", workspace_id="workspace")
        assert row.status == "ingested"
        assert row.n_chunks > 0
        assert (
            await objects.get(row.object_store_key)
            == b"# Scope\n\nThe acceptance threshold is twelve documents."
        )
        persisted = await chunks.list_for_source(row.id)
        assert "twelve documents" in persisted[0].content
        embedder.embed.assert_awaited()
        lexical.upsert_chunks.assert_awaited()
    finally:
        await selected.aclose()
        await engine.dispose()


def test_missing_native_domain_fails_actionably_instead_of_constructing_another_container():
    from pyfly.container import Container
    from pyfly.kernel import ServiceUnavailableException

    from koinon.knowledge.adapters import NativeDomains

    container = Container()
    with pytest.raises(ServiceUnavailableException, match="not enabled"):
        NativeDomains(container)._resolve(dict)


def test_retained_domain_denial_remains_an_actionable_native_denial_and_resets_scope():
    from flyquery.web.controllers.sql_execute_controller import DirectSqlForbidden
    from flyquery.web.conventions.context import current_tenant_context
    from pyfly.kernel import ForbiddenException

    from koinon.knowledge.adapters import native_scope

    with (
        pytest.raises(ForbiddenException) as raised,
        native_scope("structured", "north", "workspace", "issuer|analyst"),
    ):
        raise DirectSqlForbidden("Enable direct SQL in workspace policy before executing SQL")
    assert raised.value.code == "direct_sql_forbidden"
    assert current_tenant_context() is None


async def test_original_bytes_must_be_durable_before_document_upload_is_ready():
    from flycanon.core.services.sources.intake_service import IntakeService
    from pyfly.kernel import ServiceUnavailableException

    from koinon.knowledge.adapters import NativeDomains

    intake = SimpleNamespace(
        submit=AsyncMock(
            return_value=SimpleNamespace(
                id="source",
                status="ingested",
                n_chunks=1,
                object_store_key=None,
            )
        )
    )
    container = SimpleNamespace(
        contains_type=lambda cls: cls is IntakeService,
        resolve=lambda cls: intake,
        registered_types=lambda: [],
    )
    with pytest.raises(ServiceUnavailableException, match="original bytes"):
        await NativeDomains(configured_connections(container)).ingest_document(
            tenant_id="north",
            workspace_id="workspace",
            filename="facts.md",
            content=b"facts",
            actor="issuer|admin",
            source_catalog_id="catalog-source",
        )


async def test_structured_workspace_provisioning_preserves_catalog_uuid_through_admin_service():
    from uuid import uuid4

    from flyquery.core.services.workspaces.workspace_service import WorkspaceService
    from flyquery.web.conventions.context import current_tenant_context

    from koinon.knowledge.adapters import NativeDomains

    catalog_id = str(uuid4())

    async def provision(*, tenant_id, workspace_id, name, slug):
        assert str(workspace_id) == catalog_id and slug == catalog_id
        assert tenant_id == "north" and name == "Evidence"
        assert current_tenant_context().actor == "issuer|admin"
        return {"id": workspace_id, "tenant_id": tenant_id}

    service = SimpleNamespace(provision=AsyncMock(side_effect=provision))
    container = SimpleNamespace(
        contains_type=lambda cls: cls is WorkspaceService,
        resolve=lambda cls: service,
        registered_types=lambda: [],
    )
    result = await NativeDomains(container).ensure_workspace(
        domain="structured",
        tenant_id="north",
        catalog_id=catalog_id,
        name="Evidence",
        actor="issuer|admin",
    )
    assert result == catalog_id
    service.provision.assert_awaited_once()
    assert current_tenant_context() is None


async def test_document_search_dispatches_original_cqrs_messages_with_trusted_scope():
    from flycanon.core.services.query.handlers import AnswerKnowledgeQuery, SearchKnowledgeQuery
    from flycanon.interfaces.dtos.query import AnswerResponse, SearchResponse
    from flycanon.web.conventions.context import current_tenant_context
    from pyfly.cqrs import DefaultQueryBus

    from koinon.knowledge.adapters import NativeDomains

    async def dispatch(message):
        context = current_tenant_context()
        assert context.actor == "issuer|analyst"
        assert context.tenant_id == "north" and context.workspace_id == "workspace"
        assert message.request.source_ids == ["native-source"]
        if isinstance(message, SearchKnowledgeQuery):
            return SearchResponse(hits=[], elapsed_ms=1)
        assert isinstance(message, AnswerKnowledgeQuery)
        return AnswerResponse(
            answer="No evidence", citations=[], model="test:controlled", elapsed_ms=1, no_answer=True
        )

    bus = SimpleNamespace(query=AsyncMock(side_effect=dispatch))
    container = SimpleNamespace(
        contains_type=lambda cls: cls is DefaultQueryBus, resolve=lambda cls: bus, registered_types=lambda: []
    )
    result = await NativeDomains(configured_connections(container)).search(
        tenant_id="north",
        workspace_id="workspace",
        source_ids=["native-source"],
        question="facts",
        limit=5,
        answer=True,
        actor="issuer|analyst",
    )
    assert result["no_answer"] is True
    assert bus.query.await_count == 2
    assert current_tenant_context() is None


async def test_direct_sql_uses_retained_ast_classifier_before_resolving_an_executor():
    from uuid import uuid4

    from flyquery.core.services.datasets.dataset_service import DatasetService
    from pyfly.kernel import InvalidRequestException

    from koinon.knowledge.adapters import NativeDomains

    workspace_id, dataset_id = str(uuid4()), str(uuid4())
    datasets = SimpleNamespace(
        get=AsyncMock(return_value={"id": dataset_id, "tenant_id": "north", "workspace_id": workspace_id})
    )
    container = SimpleNamespace(
        contains_type=lambda cls: cls is DatasetService,
        resolve=lambda cls: datasets,
        registered_types=lambda: [],
    )
    with pytest.raises(InvalidRequestException, match="read-only"):
        await NativeDomains(container).query(
            tenant_id="north",
            workspace_id=workspace_id,
            dataset_id=dataset_id,
            dataset_allowlist={dataset_id},
            question="",
            conversation_id=None,
            sql="DROP TABLE facts",
            actor="issuer|analyst",
        )


async def test_direct_sql_returns_original_answer_contract_with_trusted_native_request():
    from uuid import uuid4

    from flyquery.core.services.datasets.dataset_service import DatasetService
    from flyquery.interfaces.query import AnswerResponse
    from flyquery.interfaces.sql_execute import SqlExecuteResponse
    from flyquery.web.controllers.sql_execute_controller import SqlExecuteController

    from koinon.knowledge.adapters import NativeDomains
    from koinon.web.legacy_security import trusted_legacy_context

    workspace_id, dataset_id = str(uuid4()), str(uuid4())
    datasets = SimpleNamespace(
        get=AsyncMock(return_value={"id": dataset_id, "tenant_id": "north", "workspace_id": workspace_id})
    )

    async def execute(request, body):
        context = trusted_legacy_context(request)
        assert context.actor == "issuer|analyst" and context.tenant_id == "north"
        assert context.workspace_id == workspace_id and str(body.dataset_id) == dataset_id
        return SqlExecuteResponse(
            query_id=uuid4(),
            sql=body.sql,
            ast_classification="SELECT",
            execution_status="OK",
            preview=[{"total": 12}],
            row_count=1,
            elapsed_ms=2,
        )

    executor = SimpleNamespace(execute=execute)
    registered = {DatasetService: datasets, SqlExecuteController: executor}
    container = SimpleNamespace(
        contains_type=lambda cls: cls in registered,
        resolve=lambda cls: registered[cls],
        registered_types=lambda: [],
    )
    result = await NativeDomains(container).query(
        tenant_id="north",
        workspace_id=workspace_id,
        dataset_id=dataset_id,
        dataset_allowlist={dataset_id},
        question="",
        conversation_id=None,
        sql="SELECT 12 AS total",
        actor="issuer|analyst",
    )
    assert AnswerResponse.model_validate(result).preview == [{"total": 12}]
    assert "chart_hint" in result


async def test_canonical_dataset_query_borrows_only_read_authority_even_for_an_administrator():
    from contextlib import asynccontextmanager
    from uuid import uuid4

    from flyquery.core.services.datasets.dataset_service import DatasetService
    from flyquery.core.services.query.runtime import StructuredQueryRuntimeFactory
    from flyquery.web.conventions.context import current_tenant_context

    from koinon.knowledge.adapters import NativeDomains

    workspace, dataset = str(uuid4()), str(uuid4())
    datasets = SimpleNamespace(
        get=AsyncMock(
            return_value={
                "id": dataset,
                "tenant_id": "north",
                "workspace_id": workspace,
            }
        )
    )
    observed = []

    async def answer(**arguments):
        observed.append(arguments["scopes"])
        assert current_tenant_context().actor == "issuer|administrator"
        return {"query_id": str(uuid4()), "execution_status": "OK", "sql": "SELECT 1", "snapshot_pins": {}}

    @asynccontextmanager
    async def unit(*, settings_overrides=None):
        yield SimpleNamespace(pipeline=SimpleNamespace(answer=answer))

    services = {DatasetService: datasets, StructuredQueryRuntimeFactory: SimpleNamespace(unit=unit)}
    domains = NativeDomains(
        SimpleNamespace(
            contains_type=lambda kind: kind in services,
            resolve=lambda kind: services[kind],
            registered_types=lambda: [],
        )
    )
    domains.model_requirements = lambda *arguments: ("query", ())

    @asynccontextmanager
    async def connections(*arguments, **keywords):
        yield

    domains.model_connections = connections
    await domains.query(
        tenant_id="north",
        workspace_id=workspace,
        dataset_id=dataset,
        dataset_allowlist={dataset},
        question="Count",
        conversation_id=None,
        sql=None,
        actor="issuer|administrator",
    )
    assert observed == [{"flyquery.query:read", "flyquery.sql:execute"}]


def _versioned_intake(dependencies):
    from flycanon.core.services.sources.intake_runtime import build_intake_components
    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.sources.lineage.pipeline import DocumentLineagePipeline
    from flycanon.core.services.sources.lineage.service import DocumentLineage

    pipeline = DocumentLineagePipeline(
        build_intake_components(**dependencies),
        DocumentLineage(dependencies["source_repository"], dependencies["object_store"]),
    )
    return IntakeService(**dependencies, lineage_pipeline=pipeline, intake_policy=pipeline.components.policy)
