# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Offline combined policy, native CodeAct, immutable reader, and canonical evidence proof."""

from contextlib import asynccontextmanager
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from flycanon.config import CanonSettings
from flycanon.core.agents.model_bindings import ModelBinding
from flycanon.core.services.consolidation.prompt_loader import load_prompt
from flycanon.core.services.ingestion.chunker import ParagraphChunker
from flycanon.core.services.ingestion.ingestion_service import IngestionService
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.query import rlm_answer_service
from flycanon.core.services.query.answer_dispatcher import AnswerDispatcher
from flycanon.core.services.query.answer_service import AnswerService
from flycanon.core.services.query.handlers import AnswerKnowledgeHandler, SearchKnowledgeHandler
from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
from flycanon.core.services.query.rlm.native_client import RequiredRlmBindingClient
from flycanon.core.services.query.rlm_answer_service import RLMAnswerService
from flycanon.core.services.query.search_service import SearchService
from flycanon.core.services.retrieval.retrieval_service import RetrievalService
from flycanon.core.services.sources.intake_service import IntakeService
from flycanon.core.services.storage.local_fs import LocalFsObjectStore
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.interfaces.dtos.source import SubmitSourceRequest
from flycanon.models.entities import Base
from flycanon.models.entities.source_lineage import metadata, source_extractions, source_parts
from flycanon.models.repositories import ChunkRepository, SourceRepository
from pydantic_ai.messages import ModelResponse, ToolCallPart
from pydantic_ai.models.function import FunctionModel
from pyfly.agentic.content.binary import BinaryArtifact
from pyfly.agentic.factory import AgentFactory
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.cqrs import DefaultQueryBus, HandlerRegistry
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_policy_runtime_scope import snapshot

from koinon.knowledge.adapters import NativeDomains
from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence
from koinon.knowledge.model_bindings import DomainConnections, KnowledgeConnectionResolver
from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot, snapshot_digest
from koinon.organization_knowledge.runtime import bind_snapshot


async def test_admitted_rlm_policy_executes_native_codeact_and_returns_exact_immutable_evidence(
    tmp_path, monkeypatch
):
    body = "Recorded scalar: 42"
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'combined-rlm.db'}")
    application = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "agentic": {"enabled": True},
                    "eda": {"provider": "memory"},
                }
            }
        )
    )
    await application.start()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(metadata.create_all)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        sources, chunks = SourceRepository(sessions), ChunkRepository(sessions)
        objects = LocalFsObjectStore(str(tmp_path / "objects"))
        registry = default_registry()
        baseline = CanonSettings(
            answer_mode="rag",
            store_originals=True,
            pii_policy="disabled",
            rlm_max_iters=8,
            rlm_sub_budget=12,
            rlm_max_depth=1,
        )
        baseline._agent_factory = application.get_bean(AgentFactory)
        intake = IntakeService(
            binary_normalizer=SimpleNamespace(
                normalise=AsyncMock(
                    return_value=[
                        BinaryArtifact(
                            bytes=body.encode(), kind="text", media_type="text/plain", filename="scalar.txt"
                        )
                    ]
                )
            ),
            ingestion=IngestionService(loaders=registry, chunker=ParagraphChunker()),
            loaders=registry,
            embeddings=SimpleNamespace(model="controlled-no-network", embed=AsyncMock(return_value=[[1.0]])),
            indexer=SimpleNamespace(replace_for_source=AsyncMock(return_value=1)),
            metadata_extractor=SimpleNamespace(extract=Mock(return_value=SimpleNamespace(to_dict=dict))),
            source_repository=sources,
            chunk_repository=chunks,
            audit=SimpleNamespace(record=AsyncMock()),
            event_publisher=None,
            object_store=objects,
            settings=baseline,
        )
        source = await intake.submit(
            request=SubmitSourceRequest(),
            content=b"Different preserved raw bytes",
            tenant_id="tenant",
            workspace_id="native-space",
            actor="owner",
            filename="scalar.txt",
            logical_source_key="controlled-scalar",
            operation_id="controlled-upload",
        )
        values = snapshot("tenant", "rlm", revision=7).model_dump(mode="json", exclude={"digest"})
        values["documents"].update(
            rlm_max_iters=3, rlm_sub_budget=0, rlm_max_depth=0, rlm_extended_reasoning=True
        )
        policy = OrganizationKnowledgeSnapshot.model_validate({**values, "digest": snapshot_digest(values)})
        budget_calls, model_calls, connection_calls, pre_searches = [], [], [], []
        actual_session = rlm_answer_service.RLMSession

        class ObservedSession(actual_session):
            def __init__(self, *args, **kwargs):
                budget_calls.append(dict(kwargs))
                super().__init__(*args, **kwargs)

        monkeypatch.setattr(rlm_answer_service, "RLMSession", ObservedSession)

        def respond(messages, info):
            model_calls.append(info.model_settings)
            assert [tool.name for tool in info.function_tools] == ["python"]
            code = (
                "key = docs.keys()[0]\ntext = docs[key]\n"
                "value = text.rsplit(': ', 1)[1]\nfinal(value, filings=[key], pages=[0])"
            )
            return ModelResponse(parts=[ToolCallPart("python", {"code": code}, "controlled-python")])

        model = FunctionModel(respond)

        @asynccontextmanager
        async def resolve(**scope):
            assert (
                scope["domain"],
                scope["tenant_id"],
                scope["workspace_id"],
                scope["subject"],
                scope["purpose"],
                scope["roles"],
            ) == ("canon", "tenant", "native-space", "owner", "rlm", ("documents.rlm",))
            connection_calls.append(scope)
            yield DomainConnections(
                {
                    "documents.rlm": ModelBinding(
                        model, {"temperature": 0.0, "max_tokens": 96}, "openai", "responses"
                    )
                },
                {},
            )

        retrieval = RetrievalService(
            context=SimpleNamespace(),
            embeddings=SimpleNamespace(),
            source_repository=sources,
            chunk_repository=chunks,
            knowledge_repository=None,
            default_top_k=10,
            default_per_query_k=30,
            rrf_k=60,
        )

        async def forbidden_search(**kwargs):
            pre_searches.append(kwargs)
            raise AssertionError("The selected RLM engine must not pre-run hybrid/RAG retrieval")

        retrieval.search = forbidden_search
        rag = AnswerService(
            retrieval=retrieval,
            prompt=load_prompt("answer"),
            default_model=baseline.answer_model,
            fallback_model=None,
            settings=baseline,
        )
        rlm = RLMAnswerService(
            corpus_builder=CanonCorpusBuilder(
                source_repository=sources, knowledge_repository=None, object_store=objects, registry=registry
            ),
            client=RequiredRlmBindingClient(),
            settings=baseline,
            cost_service=SimpleNamespace(record=AsyncMock()),
        )
        dispatcher = AnswerDispatcher(rag=rag, rlm=rlm, settings=baseline)
        handlers = HandlerRegistry()
        handlers.register_query_handler(AnswerKnowledgeHandler(dispatcher))
        handlers.register_query_handler(SearchKnowledgeHandler(SearchService(retrieval=retrieval), baseline))
        bus = DefaultQueryBus(handlers, caching_enabled=False)
        beans = {
            DefaultQueryBus: bus,
            CanonSettings: baseline,
            SourceRepository: sources,
            ObjectStore: objects,
            KnowledgeConnectionResolver: SimpleNamespace(resolve=resolve),
        }
        domains = NativeDomains(
            SimpleNamespace(
                contains_type=lambda kind: kind in beans,
                resolve=lambda kind: beans[kind],
                registered_types=list,
            )
        )
        asset = SimpleNamespace(id="asset", kind="document", name="Controlled scalar", workspace_id="space")
        parent = SimpleNamespace(id="canonical-source")
        binding = SimpleNamespace(native_id=source.id, native_workspace_id="native-space")

        # Only canonical authorization and ID projection are fixture seams; native reads and proofs are real.
        class CanonicalSeam:
            async def _chain(self, subject, tenant, asset_id, *permissions):
                assert (subject, tenant, asset_id) == ("owner", "tenant", "asset")
                return [asset, parent]

            async def binding(self, tenant, asset_id, domain, *, entry):
                assert (tenant, asset_id, domain, entry.id) == ("tenant", "asset", "canon", "asset")
                return binding

            async def search(self, subject, tenant, **arguments):
                receipt = arguments["_capture"]
                receipt.admit_documents(tenant, "native-space", subject, {source.id: (asset, parent)})

                async def authorize():
                    await self._chain(subject, tenant, asset.id, "knowledge:search")

                receipt.authorize_model = authorize
                with bind_snapshot(policy, subject):
                    result = await domains.search(
                        tenant_id=tenant,
                        workspace_id="native-space",
                        catalog_workspace_id="space",
                        source_ids=[source.id],
                        question=arguments["question"],
                        limit=10,
                        answer=True,
                        actor=subject,
                        _capture=receipt,
                        _knowledge_settings_snapshot=policy,
                    )
                return {
                    "answer": result["answer"],
                    "hits": [
                        {
                            "id": hit["chunk_id"],
                            "asset_id": asset.id,
                            "source_id": parent.id,
                            "text": hit["content"],
                            "title": asset.name,
                            "score": hit["score"],
                        }
                        for hit in result["hits"]
                    ],
                    "citations": [
                        {**citation, "asset_id": asset.id, "source_id": parent.id}
                        for citation in result["citations"]
                    ],
                }

        canonical = CanonicalSeam()
        canonical.domains = domains
        result = await NativeKnowledgeEvidence(canonical, SimpleNamespace()).search(
            "owner", "tenant", question="What is the recorded scalar?", answer=True
        )
        assert result.complete and result.data["answer"] == "42"
        assert (
            len(result.sources) == 1 and len(model_calls) == len(connection_calls) == len(budget_calls) == 1
        )
        assert pre_searches == []
        assert {
            key: budget_calls[0][key] for key in ("max_iters", "sub_budget", "max_depth", "sandbox_mode")
        } == {"max_iters": 6, "sub_budget": 0, "max_depth": 0, "sandbox_mode": "subprocess"}
        assert model_calls == [{"temperature": 0.0, "max_tokens": 96}]
        assert (
            baseline.answer_mode,
            baseline.rlm_max_iters,
            baseline.rlm_sub_budget,
            baseline.rlm_max_depth,
        ) == ("rag", 8, 12, 1)
        recorded = result.sources[0]
        assert recorded.quote == body and recorded.source_part_sha256 == sha256(body.encode()).hexdigest()
        assert (
            recorded.chunk_id is None and recorded.page is None and recorded.page_basis == "recorded_loader"
        )
        assert recorded.asset_id == "asset" and recorded.source_id == "canonical-source"
        assert recorded.availability == "available"
        async with sessions() as session:
            part = (
                (
                    await session.execute(
                        select(source_parts).where(source_parts.c.id == recorded.source_part_id)
                    )
                )
                .mappings()
                .one()
            )
            view = (
                (
                    await session.execute(
                        select(source_extractions).where(source_extractions.c.id == recorded.extraction_id)
                    )
                )
                .mappings()
                .one()
            )
        assert (
            part["source_id"],
            part["extraction_id"],
            part["sha256"],
            view["purpose"],
            view["version_id"],
        ) == (
            source.id,
            recorded.extraction_id,
            recorded.source_part_sha256,
            "whole_document_read",
            recorded.source_version_id,
        )
        citation = result.data["citations"][0]
        assert citation["metadata"]["source_part_id"] == recorded.source_part_id
        assert citation["metadata"]["source_part_sha256"] == recorded.source_part_sha256
        assert any(read.stage == "rlm.root" for read in result.native_reads)
        assert any(
            read.stage == "rlm.read"
            and read.content_sha256 == sha256(body.encode()).hexdigest()
            and read.source_version_id == recorded.source_version_id
            and read.extraction_id == recorded.extraction_id
            for read in result.native_reads
        )
    finally:
        await application.stop()
        await engine.dispose()
