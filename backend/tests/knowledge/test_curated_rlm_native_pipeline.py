# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Managed curated publication and real native CodeAct, with an offline FunctionModel."""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_curated_intents import curated as curated
from test_curated_intents import input_for
from test_curated_native_commit import transaction_fixture
from test_curated_native_events import native_lifecycle as native_lifecycle
from test_policy_runtime_scope import snapshot


@pytest.mark.parametrize("typed_terminal", [False, True])
async def test_native_curated_rlm_reads_exact_published_version_and_never_republishes(
    curated, native_lifecycle, typed_terminal
):
    from flycanon.config import CanonSettings
    from flycanon.core.agents.model_bindings import ModelBinding
    from flycanon.core.services.query.answer_dispatcher import AnswerDispatcher
    from flycanon.core.services.query.answer_service import AnswerService
    from flycanon.core.services.query.handlers import AnswerKnowledgeHandler
    from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
    from flycanon.core.services.query.rlm.native_client import RequiredRlmBindingClient
    from flycanon.core.services.query.rlm_answer_service import RLMAnswerService
    from flycanon.core.services.retrieval.retrieval_service import RetrievalService
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
    from pydantic_ai.messages import ModelResponse, ToolCallPart, ToolReturnPart
    from pydantic_ai.models.function import FunctionModel
    from pyfly.agentic.factory import AgentFactory
    from pyfly.container import Container
    from pyfly.context import ApplicationContext
    from pyfly.core import Config
    from pyfly.cqrs import DefaultQueryBus, HandlerRegistry
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import infrastructure_unit
    from pyfly.data.transaction.registry import install_registry, installed_registry
    from sqlalchemy import func, select

    from koinon.knowledge.adapters import NativeDomains
    from koinon.knowledge.curated.acknowledgement import CatalogAcknowledgement
    from koinon.knowledge.curated.corpus import CuratedBodyCorpus
    from koinon.knowledge.curated.ports import NativeCatalogProjection, NativeKnowledgeOperation
    from koinon.knowledge.curated.reads import CuratedKnowledgeReads
    from koinon.knowledge.curated.whole_repository import CuratedWholePartRepository
    from koinon.knowledge.entities import DomainBinding
    from koinon.knowledge.evidence_capture import NativeKnowledgeEvidence
    from koinon.knowledge.model_bindings import DomainConnections, KnowledgeConnectionResolver
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings
    from koinon.organization_knowledge.runtime import bind_snapshot
    from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings

    service, destination, unit = await transaction_fixture(curated, native_lifecycle)
    _, catalog, _, context = curated
    native = native_lifecycle[1]
    primary = context.get_bean(DataSourceRegistry).get("primary")
    async with infrastructure_unit(primary) as session:
        session.add(
            DomainBinding(
                id="workspace-alias",
                tenant_id="north",
                catalog_id=destination.workspace_id,
                workspace_id=destination.workspace_id,
                domain="canon",
                entity_kind="workspace",
                native_id="owned",
                native_workspace_id="owned",
                created_by="issuer|owner",
            )
        )
    preview = await service.preview(
        "issuer|owner", "north", input_for(destination, action="create_published")
    )
    published = await unit.commit(NativeKnowledgeOperation(preview, ()), native_workspace_id="owned")
    acknowledgement = context.get_bean(CatalogAcknowledgement)
    projection = NativeCatalogProjection(
        native_workspace_id="owned",
        title=preview.after.title,
        serving_version_id=published.native_version_id,
        serving_operation_id=published.operation_id,
    )
    await acknowledgement.apply(preview, published, projection)
    if typed_terminal:
        service.native = SimpleNamespace(
            get=lambda: SimpleNamespace(head=lambda *args: unit.head("north", "owned", published.item_id))
        )
        draft = await service.preview(
            "issuer|owner",
            "north",
            input_for(
                destination,
                action="update_draft",
                target_item_id=published.item_id,
                expected_version=1,
                content={"title": "Unpublished rule", "body": "The threshold is 99."},
            ),
        )
        draft_receipt = await unit.commit(NativeKnowledgeOperation(draft, ()), native_workspace_id="owned")
        await acknowledgement.apply(draft, draft_receipt, projection)
    reads = context.get_bean(CuratedKnowledgeReads)
    reads.native = SimpleNamespace(datasource=lambda: native)
    context.get_bean(CuratedWholePartRepository).datasources = native.registry
    corpus = context.get_bean(CuratedBodyCorpus)
    factory = ApplicationContext(
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
    data_registry = installed_registry()
    await factory.start()
    assert data_registry is not None
    install_registry(data_registry)
    try:
        settings = CanonSettings(answer_mode="rag", rlm_max_iters=3, rlm_sub_budget=0, rlm_max_depth=0)
        settings._agent_factory = factory.get_bean(AgentFactory)
        calls = []

        def respond(messages, info):
            calls.append(info.model_settings)
            assert [tool.name for tool in info.function_tools] == ["python", "final_answer"]
            if typed_terminal and len(calls) == 2:
                returned = [
                    part for message in messages for part in message.parts if isinstance(part, ToolReturnPart)
                ][-1]
                key, value = returned.content.strip().splitlines()
                return ModelResponse(
                    parts=[
                        ToolCallPart(
                            "final_answer", {"answer": value, "filings": [key], "pages": [0]}, "curated-final"
                        )
                    ]
                )
            code = (
                "key = docs.keys()[0]\ntext = docs.get(key)\nvalue = text.rsplit(' ', 1)[1].rstrip('.')\n"
                + ("print(key); print(value)" if typed_terminal else "final(value, filings=[key], pages=[0])")
            )
            return ModelResponse(parts=[ToolCallPart("python", {"code": code}, "curated-python")])

        model = FunctionModel(respond)

        @asynccontextmanager
        async def resolve(**scope):
            assert (
                scope["tenant_id"],
                scope["workspace_id"],
                scope["subject"],
                scope["purpose"],
                scope["roles"],
            ) == ("north", "owned", "issuer|reader", "rlm", ("documents.rlm",))
            yield DomainConnections(
                {
                    "documents.rlm": ModelBinding(
                        model, {"temperature": 0.0, "max_tokens": 96}, "openai", "responses"
                    )
                },
                {},
            )

        def forbidden(*args, **kwargs):
            pytest.fail("Curated-only RLM must not query documents, original objects, embeddings or RAG")

        builder = CanonCorpusBuilder(
            source_repository=SimpleNamespace(list_active=forbidden),
            knowledge_repository=SimpleNamespace(list_sources=forbidden),
            object_store=SimpleNamespace(get_sync=forbidden),
        )
        rlm = RLMAnswerService(
            corpus_builder=builder,
            client=RequiredRlmBindingClient(),
            settings=settings,
            cost_service=SimpleNamespace(record=AsyncMock()),
        )
        retrieval = RetrievalService(
            context=SimpleNamespace(),
            embeddings=SimpleNamespace(embed=forbidden),
            source_repository=SimpleNamespace(),
            chunk_repository=SimpleNamespace(),
            knowledge_repository=None,
            default_top_k=10,
            default_per_query_k=30,
            rrf_k=60,
        )
        retrieval.search = forbidden
        rag = AnswerService(
            retrieval=retrieval,
            prompt="RAG must not run",
            default_model=settings.answer_model,
            fallback_model=None,
            settings=settings,
        )
        dispatcher = AnswerDispatcher(rag=rag, rlm=rlm, settings=settings)
        handlers = HandlerRegistry()
        handlers.register_query_handler(AnswerKnowledgeHandler(dispatcher))
        container = Container()
        container.register_instance(CanonSettings, settings)
        container.register_instance(DefaultQueryBus, DefaultQueryBus(handlers, caching_enabled=False))
        container.register_instance(KnowledgeConnectionResolver, SimpleNamespace(resolve=resolve))
        domains = NativeDomains(container, WorkAdmission(WorkAdmissionSettings()))
        facade = KnowledgeFacade(
            catalog,
            context.get_bean(DomainBindingRepository),
            domains,
            KnowledgeSettings(),
            curated=SimpleNamespace(get=lambda: corpus),
        )
        evidence = NativeKnowledgeEvidence(facade, context.get_bean(DataSourceRegistry))
        with bind_snapshot(snapshot("north", "rlm", revision=7), "issuer|reader"):
            result = await evidence.search(
                "issuer|reader",
                "north",
                question="What is the renewal threshold?",
                asset_ids=[published.item_id],
                answer=True,
            )
        assert result.complete and result.data["answer"] == "47"
        assert result.data["knowledge_settings_snapshot"]["revision"] == 7
        assert len(result.sources) == 1 and result.sources[0].kind == "knowledge_version"
        source = result.sources[0]
        assert (source.asset_id, source.knowledge_version_id, source.knowledge_version) == (
            published.item_id,
            published.native_version_id,
            1,
        )
        assert (
            source.quote == preview.after.body
            and source.source_id is source.page is source.extraction_id is None
        )
        assert {row.domain for row in result.native_reads} == {"knowledge"}
        assert {"rlm.knowledge_view.v1", "rlm.read", "rlm.execution_read.v1", "rlm.root"} <= {
            row.stage for row in result.native_reads
        }
        assert len(result.rlm_tools) == len(calls) == (2 if typed_terminal else 1)
        assert all(
            row.source_ids == () and row.knowledge_item_ids == (published.item_id,)
            for row in result.rlm_tools
        )
        async with infrastructure_unit(native, read_only=True) as session:
            assert await session.scalar(select(func.count()).select_from(KnowledgeVersionRow)) == (
                2 if typed_terminal else 1
            )
    finally:
        await factory.stop()
