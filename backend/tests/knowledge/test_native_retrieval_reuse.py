# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Candidate reuse must preserve authority, immutable evidence and independent result limits."""

from collections import Counter
from contextlib import asynccontextmanager
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest
from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import ModelBinding
from flycanon.core.services.consolidation.prompt_loader import load_prompt
from flycanon.core.services.ingestion.chunker import ParagraphChunker
from flycanon.core.services.ingestion.ingestion_service import IngestionService
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.metadata import MetadataExtractor
from flycanon.core.services.query.answer_dispatcher import AnswerDispatcher
from flycanon.core.services.query.answer_service import AnswerService
from flycanon.core.services.query.handlers import AnswerKnowledgeHandler, SearchKnowledgeHandler
from flycanon.core.services.query.search_service import SearchService
from flycanon.core.services.retrieval.corpus_factory import CorpusContext
from flycanon.core.services.retrieval.fusion import ChunkHit, StoredChunk
from flycanon.core.services.retrieval.retrieval_service import RetrievalService
from flycanon.core.services.sources.lineage.service import DocumentLineage
from flycanon.core.services.storage.local_fs import LocalFsObjectStore
from flycanon.interfaces.dtos.source import SubmitSourceRequest
from flycanon.models.entities import Base
from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
from flycanon.models.entities.source_lineage import metadata
from flycanon.models.repositories import ChunkRepository, KnowledgeRepository, SourceRepository
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pyfly.agentic.content.binary import BinaryConfig, BinaryNormalizer
from pyfly.agentic.factory import AgentFactory
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.cqrs import DefaultQueryBus, HandlerRegistry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_policy_runtime_scope import snapshot
from test_rlm_policy_pipeline import _versioned_intake

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.adapters import NativeDomains
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.knowledge.model_bindings import DomainConnections, KnowledgeConnectionResolver
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot, snapshot_digest
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings


@pytest.fixture
async def native_retrieval(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'retrieval.db'}")
    application = ApplicationContext(
        Config({"pyfly": {"banner": {"mode": "off"}, "agentic": {"enabled": True}}})
    )
    await application.start()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    sources, chunks = SourceRepository(sessions), ChunkRepository(sessions)
    objects, loaders = LocalFsObjectStore(str(tmp_path / "objects")), default_registry()
    settings = CanonSettings(_env_file=None, store_originals=True, pii_policy="disabled", answer_mode="rag")
    settings._agent_factory = application.get_bean(AgentFactory)
    intake = _versioned_intake(
        dict(
            binary_normalizer=BinaryNormalizer(config=BinaryConfig()),
            ingestion=IngestionService(loaders=loaders, chunker=ParagraphChunker()),
            loaders=loaders,
            embeddings=NS(model="controlled", embed=AsyncMock(return_value=[[1.0]])),
            indexer=NS(replace_for_source=AsyncMock(return_value=1)),
            metadata_extractor=MetadataExtractor(),
            source_repository=sources,
            chunk_repository=chunks,
            audit=NS(record=AsyncMock()),
            event_publisher=None,
            object_store=objects,
            settings=settings,
        )
    )
    ids = []
    for number in (42, 59):
        source = await intake.submit(
            request=SubmitSourceRequest(),
            content=f"Review every {number} days.".encode(),
            tenant_id="tenant",
            workspace_id="space",
            actor="owner",
            filename=f"{number}.txt",
            logical_source_key=f"rule-{number}",
            operation_id=f"upload-{number}",
        )
        ids.append(source.id)
    async with sessions() as session:
        rows = list(
            (await session.scalars(select(KnowledgeChunkRow).order_by(KnowledgeChunkRow.content))).all()
        )
    calls = Counter()
    state = NS(allowed=True, after_search=None, fail_dense_once=False)

    class Corpus:
        async def bm25_search(self, query, *, top_k, source_ids=None, **scope):
            calls["lexical"] += 1
            return [
                ChunkHit(r.id, 1, r.content, doc_id=r.source_id) for r in rows if r.source_id in source_ids
            ][:top_k]

        async def get_chunks(self, chunk_ids, **scope):
            calls["candidate_hydration"] += 1
            return [
                StoredChunk(
                    r.id, r.source_id, r.source_id, 0, r.content, metadata=dict(r.metadata_json or {})
                )
                for r in rows
                if r.id in chunk_ids
            ]

    class Vectors:
        async def search(self, vector, *, top_k, filters=None, **scope):
            calls["dense"] += 1
            if state.fail_dense_once:
                state.fail_dense_once = False
                raise RuntimeError("Owned vector transport unavailable")
            selected = next(f.value for f in filters if f.field == "source_id")
            return [NS(document=NS(id=r.id)) for r in rows if r.source_id in selected][:top_k]

    class Embedder:
        async def embed_one(self, query):
            calls["embedding"] += 1
            return [1.0]

    retrieval = RetrievalService(
        context=CorpusContext(Corpus(), Vectors(), "controlled"),
        embeddings=Embedder(),
        source_repository=sources,
        chunk_repository=chunks,
        knowledge_repository=KnowledgeRepository(sessions),
        default_top_k=10,
        default_per_query_k=30,
        rrf_k=60,
    )

    def respond(messages, info):
        calls["model"] += 1
        return ModelResponse(
            parts=[ToolCallPart("final_result", {"answer": "42 days", "citation_chunk_ids": [rows[0].id]})]
        )

    @asynccontextmanager
    async def resolve(**scope):
        yield DomainConnections(
            {"documents.answer": ModelBinding(FunctionModel(respond), {"max_tokens": 200}, "openai", "chat")},
            {},
        )

    answer = AnswerService(
        retrieval=retrieval,
        prompt=load_prompt("answer"),
        default_model=settings.answer_model,
        fallback_model=None,
        settings=settings,
    )
    handlers = HandlerRegistry()
    handlers.register_query_handler(SearchKnowledgeHandler(SearchService(retrieval=retrieval), settings))
    handlers.register_query_handler(
        AnswerKnowledgeHandler(AnswerDispatcher(rag=answer, rlm=NS(), settings=settings))
    )
    actual_bus = DefaultQueryBus(handlers, caching_enabled=False)

    class Bus:
        async def query(self, query):
            result = await actual_bus.query(query)
            if type(query).__name__ == "SearchKnowledgeQuery" and state.after_search is not None:
                await state.after_search()
            return result

    beans = {
        DefaultQueryBus: Bus(),
        CanonSettings: settings,
        DocumentLineage: DocumentLineage(sources, objects),
        KnowledgeConnectionResolver: NS(resolve=resolve),
    }
    domains = NativeDomains(
        NS(contains_type=lambda kind: kind in beans, resolve=lambda kind: beans[kind], registered_types=list),
        admission=WorkAdmission(WorkAdmissionSettings()),
    )

    async def run(*, limit=10, answer_top_k=10):
        values = snapshot("tenant", "rag").model_dump(mode="json", exclude={"digest"})
        values["documents"].update(answer_top_k=answer_top_k)
        policy = OrganizationKnowledgeSnapshot.model_validate({**values, "digest": snapshot_digest(values)})
        receipt = NativeEvidenceReceipt("owner", "tenant", operation="search")
        receipt.admit_documents(
            "tenant",
            "space",
            "owner",
            {sid: (NS(id=sid, workspace_id="space", name="rule"), NS(id="source")) for sid in ids},
        )

        async def authorize():
            calls["authorize"] += 1
            if not state.allowed:
                raise AccessDenied("Revoked")

        receipt.authorize_model = authorize
        return await domains.search(
            tenant_id="tenant",
            workspace_id="space",
            source_ids=ids,
            question="review",
            limit=limit,
            answer=True,
            actor="owner",
            _capture=receipt,
            _knowledge_settings_snapshot=policy,
        )

    try:
        yield NS(
            run=run,
            calls=calls,
            state=state,
            retrieval=retrieval,
            sessions=sessions,
            rows=rows,
            ids=ids,
            lineage=beans[DocumentLineage],
        )
    finally:
        await application.stop()
        await engine.dispose()


async def test_default_reuses_candidates_preserving_full_hits_and_immutable_citations(native_retrieval):
    f = native_retrieval
    result = await f.run()
    assert len(result["hits"]) == 2 and len(result["citations"]) == 1
    assert result["citations"][0]["metadata"]["source_part_sha256"]
    assert "42" in result["answer"]
    assert {key: f.calls[key] for key in ("embedding", "dense", "lexical", "model")} == {
        "embedding": 1,
        "dense": 1,
        "lexical": 1,
        "model": 1,
    }


@pytest.mark.parametrize("arguments", [{"limit": 11}, {"answer_top_k": 1}])
async def test_different_limits_keep_both_retrievals(native_retrieval, arguments):
    f = native_retrieval
    result = await f.run(**arguments)
    assert len(result["hits"]) == 2 and len(result["citations"]) == 1
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 2


async def test_revocation_between_passes_denies_before_second_embedding_or_model(native_retrieval):
    f = native_retrieval

    async def revoke():
        f.state.allowed = False

    f.state.after_search = revoke
    with pytest.raises(Exception, match="Revoked"):
        await f.run()
    assert f.calls["model"] == 0
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 1


async def test_finished_operation_cannot_reuse_previous_candidates(native_retrieval):
    f = native_retrieval
    await f.run()
    await f.run()
    assert f.calls["model"] == 2
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 2


async def test_degraded_first_retrieval_is_not_reused(native_retrieval):
    f = native_retrieval
    f.state.fail_dense_once = True
    result = await f.run()
    assert len(result["hits"]) == 2 and len(result["citations"]) == 1
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 2


async def test_failed_operation_discards_its_candidates(native_retrieval):
    f = native_retrieval

    async def interrupt():
        raise RuntimeError("Interrupted after search")

    f.state.after_search = interrupt
    with pytest.raises(RuntimeError, match="Interrupted after search"):
        await f.run()
    f.state.after_search = None
    await f.run()
    assert f.calls["model"] == 1
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 2


async def test_reused_candidates_still_rehydrate_and_verify_immutable_content(native_retrieval):
    f = native_retrieval

    async def change_projection():
        async with f.sessions() as session:
            row = await session.get(KnowledgeChunkRow, f.rows[0].id)
            row.content = "Unverified changed projection"
            await session.commit()

    f.state.after_search = change_projection
    with pytest.raises(Exception, match="immutable ingestion chunk"):
        await f.run()
    assert f.calls["model"] == 0
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 1


@asynccontextmanager
async def candidate_operation(fixture, *, digest="policy-one", subject="owner", embeddings=None):
    from flycanon.core.agents.model_bindings import push_bindings, reset_bindings
    from flycanon.core.services.query import provenance
    from flycanon.core.services.retrieval.candidate_reuse import candidate_scope

    from koinon.knowledge.adapters import native_scope

    async def authorize():
        fixture.calls["authorize"] += 1
        if not fixture.state.allowed:
            raise AccessDenied("Revoked")

    receipt = NativeEvidenceReceipt(subject, "tenant", operation="search")
    receipt.admit_documents(
        "tenant",
        "space",
        subject,
        {sid: (NS(id=sid, workspace_id="space", name="rule"), NS(id="source")) for sid in fixture.ids},
    )
    receipt.authorize_model = authorize
    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.core.services.sources.lineage.retrieval import bind_retrieval_parts

    async def parts(hits, scope):
        return await bind_retrieval_parts(fixture.lineage, DocumentScope("tenant", "space", subject), hits)

    receipt.resolve_document_retrieval_parts = parts
    with native_scope("canon", "tenant", "space", subject):
        token = push_bindings(
            tenant_id="tenant", workspace_id="space", subject=subject, bindings={}, embeddings=embeddings
        )
        try:
            with (
                provenance.observe(receipt, tenant_id="tenant", workspace_id="space", actor=subject),
                candidate_scope(policy_digest=digest),
            ):
                yield
        finally:
            reset_bindings(token)


def direct_arguments(fixture):
    from flycanon.core.services.retrieval.retrieval_service import RetrievalFilters

    return dict(
        query="review",
        tenant_id="tenant",
        workspace_id="space",
        top_k=10,
        per_query_k=30,
        filters=RetrievalFilters(source_ids=fixture.ids),
    )


@pytest.mark.parametrize(
    "change", ["query", "top_k", "per_query_k", "source_ids", "statuses", "rrf", "embedder", "corpus"]
)
async def test_different_effective_request_or_resources_do_not_reuse(native_retrieval, change):
    from copy import copy

    from flycanon.core.services.retrieval.retrieval_service import RetrievalFilters

    f = native_retrieval
    arguments = direct_arguments(f)
    async with candidate_operation(f):
        await f.retrieval.search(**arguments)
        if change == "query":
            arguments["query"] = "different review"
        elif change in {"top_k", "per_query_k"}:
            arguments[change] += 1
        elif change == "source_ids":
            arguments["filters"] = RetrievalFilters(source_ids=f.ids[:1])
        elif change == "statuses":
            arguments["filters"] = RetrievalFilters(source_ids=f.ids, statuses=["published"])
        elif change == "rrf":
            f.retrieval._rrf_k += 1
        elif change == "embedder":
            f.retrieval._embeddings = copy(f.retrieval._embeddings)
        elif change == "corpus":
            f.retrieval._context.corpus = copy(f.retrieval._context.corpus)
        await f.retrieval.search(**arguments)
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 2


async def test_inherited_task_cannot_read_or_retain_parent_candidates(native_retrieval):
    import asyncio

    f = native_retrieval
    arguments = direct_arguments(f)
    async with candidate_operation(f):
        await f.retrieval.search(**arguments)
        with pytest.raises(Exception, match="operation has ended|provenance scope has expired"):
            await asyncio.create_task(f.retrieval.search(**arguments))
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 1


async def test_child_cannot_reuse_after_parent_operation_closed(native_retrieval):
    import asyncio

    f = native_retrieval
    arguments = direct_arguments(f)
    release = asyncio.Event()

    async def child():
        await release.wait()
        return await f.retrieval.search(**arguments)

    async with candidate_operation(f):
        await f.retrieval.search(**arguments)
        task = asyncio.create_task(child())
    release.set()
    with pytest.raises(
        Exception, match="operation has ended|lifetime has ended|provenance scope has expired"
    ):
        await task
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 1


async def test_authorization_finishing_after_scope_closed_cannot_release_candidates(native_retrieval):
    from flycanon.core.services.retrieval import candidate_reuse

    f = native_retrieval
    arguments = direct_arguments(f)
    async with candidate_operation(f):
        await f.retrieval.search(**arguments)
        scope = candidate_reuse._current.get()

        async def close():
            scope.active = False

        scope.observation.observer.authorize = close
        with pytest.raises(Exception, match="operation has ended"):
            await f.retrieval.search(**arguments)
    assert f.calls["embedding"] == 1


async def test_replacement_model_binding_cannot_borrow_previous_candidates(native_retrieval):
    from flycanon.core.agents.model_bindings import push_bindings, reset_bindings

    f = native_retrieval
    async with candidate_operation(f):
        await f.retrieval.search(**direct_arguments(f))
        token = push_bindings(tenant_id="tenant", workspace_id="space", subject="owner", bindings={})
        try:
            with pytest.raises(Exception, match="operation has ended"):
                await f.retrieval.search(**direct_arguments(f))
        finally:
            reset_bindings(token)
    assert f.calls["embedding"] == 1


async def test_policy_and_actor_operations_cannot_reuse_previous_candidates(native_retrieval):
    f = native_retrieval
    for digest, subject in (("one", "owner"), ("two", "owner"), ("two", "another")):
        async with candidate_operation(f, digest=digest, subject=subject):
            await f.retrieval.search(**direct_arguments(f))
            await f.retrieval.search(**direct_arguments(f))
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 3


async def test_reuse_reloads_custom_corpus_metadata_and_stores_no_content(native_retrieval):
    from flycanon.core.services.retrieval import candidate_reuse

    f = native_retrieval
    async with candidate_operation(f):
        first = await f.retrieval.search(**direct_arguments(f))
        f.rows[0].metadata_json = {"custom_runtime_tag": "changed-between-passes"}
        second = await f.retrieval.search(**direct_arguments(f))
        assert "custom_runtime_tag" not in first.hits[0].metadata
        assert second.hits[0].metadata["custom_runtime_tag"] == "changed-between-passes"
        retained = candidate_reuse._current.get().candidates
        assert all(set(vars(candidate)) <= {"chunk_id", "score"} for candidate in retained)
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 1
    assert f.calls["candidate_hydration"] == 2


async def test_changed_active_embedding_set_keeps_second_retrieval(native_retrieval):
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetBinding

    f = native_retrieval
    embedder = f.retrieval._embeddings
    embedder.model, embedder.dimensions = "openai:controlled", 3
    selected = EmbeddingSetBinding("first", "openai", "controlled", 3)

    async def active(**scope):
        return selected

    f.retrieval._embedding_sets = NS(active_binding=active)
    f.retrieval._embedding_registry = NS(default=embedder, for_binding=lambda binding: embedder)
    async with candidate_operation(f):
        await f.retrieval.search(**direct_arguments(f))
        selected = EmbeddingSetBinding("replacement", "openai", "controlled", 3)
        await f.retrieval.search(**direct_arguments(f))
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 2


@pytest.mark.parametrize("feature", ["expansion", "reranker"])
async def test_optional_model_retrieval_stages_remain_ineligible(native_retrieval, feature):
    f = native_retrieval
    if feature == "expansion":

        async def expand(query, *, n):
            return [query]

        f.retrieval._query_expander = NS(expand=expand)
        f.retrieval._query_expansion_n = 2
    else:

        async def rerank(*, query, hits, top_n):
            return hits[:top_n]

        f.retrieval._reranker = NS(rerank=rerank)
    async with candidate_operation(f):
        await f.retrieval.search(**direct_arguments(f))
        await f.retrieval.search(**direct_arguments(f))
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 2


async def test_actual_borrowed_embedding_registry_wrappers_share_only_the_same_profile(native_retrieval):
    from flycanon.core.agents.model_bindings import EmbeddingBinding
    from flycanon.core.services.embeddings.embedding_service import EmbeddingRegistry
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetBinding
    from pyfly.agentic.embeddings import BaseEmbedder

    f = native_retrieval

    class Provider(BaseEmbedder):
        async def _embed_batch(self, texts, **kwargs):
            f.calls["embedding"] += 1
            return [[1.0] + [0.0] * 63 for _ in texts]

    provider = Provider(model="controlled", dimensions=64)
    selected = EmbeddingSetBinding("owned", "openai", "controlled", 64)
    settings = CanonSettings(_env_file=None, embedding_model="openai:controlled", embedding_dimensions=64)
    settings._require_model_bindings = True
    wrappers = []

    class ObservedRegistry(EmbeddingRegistry):
        def for_binding(self, binding):
            selected = super().for_binding(binding)
            wrappers.append(selected)
            return selected

    registry = ObservedRegistry(settings=settings)

    async def active(**scope):
        return selected

    f.retrieval._embedding_sets = NS(active_binding=active)
    f.retrieval._embedding_registry = registry
    connections = {"documents.embedding": EmbeddingBinding(provider, "openai:controlled", 64, 64, "owned")}
    async with candidate_operation(f, embeddings=connections):
        first = await f.retrieval.search(**direct_arguments(f))
        second = await f.retrieval.search(**direct_arguments(f))
    assert len(wrappers) == 2 and wrappers[0] is not wrappers[1]
    assert [h.content for h in first.hits] == [h.content for h in second.hits]
    assert f.calls["embedding"] == f.calls["dense"] == f.calls["lexical"] == 1
