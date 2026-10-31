# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic_ai.models.test import TestModel
from pyfly.agentic.config import AgenticConfig
from pyfly.kernel import ServiceUnavailableException


@pytest.fixture(
    params=[
        ("flycanon", "documents.answer", "flycanon-answerer"),
        ("flyquery", "structured.generation", "flyquery-generation"),
    ]
)
def domain(request):
    package, role, stage = request.param
    return package, role, stage, import_module(package + ".core.agents.model_bindings")


def enter_context(package, tenant="north", subject="issuer|north"):
    module = import_module(package + ".web.conventions.context")
    token = module.set_tenant_context(
        module.TenantContext(
            tenant_id=tenant, workspace_id="workspace", actor=subject, correlation_id="model-test"
        )
    )
    return token


async def test_bound_stage_uses_only_selected_native_model_settings_and_output_mode(domain):
    package, role, stage, port = domain
    model = TestModel()
    binding = port.ModelBinding(
        model=model,
        model_settings={"temperature": 0.25, "max_tokens": 1200},
        provider="ollama",
        api="chat",
        output_mode="native",
    )
    factory = SimpleNamespace(
        runtime=SimpleNamespace(config=AgenticConfig()), create=MagicMock(return_value=object())
    )
    settings = SimpleNamespace(_agent_factory=factory, agent_max_output_tokens=8192)
    context = enter_context(package)
    token = port.push_bindings(
        tenant_id="north", workspace_id="workspace", subject="issuer|north", bindings={role: binding}
    )
    try:
        builder = import_module(package + ".core.agents.builder")
        builder.build_agent(
            name=stage,
            model="openai:must-never-resolve",
            output_type=dict,
            instructions="Evidence",
            settings=settings,
        )
        options = factory.create.call_args.kwargs
        assert options["model"] is model
        assert options["model_settings"] == {"temperature": 0.25, "max_tokens": 1200}
        assert type(options["output_type"]).__name__ == "NativeOutput"
    finally:
        port.reset_bindings(token)
        context.var.reset(context.token)


async def test_required_scope_missing_or_foreign_binding_fails_before_agent_creation(domain):
    package, role, stage, port = domain
    factory = SimpleNamespace(runtime=SimpleNamespace(config=AgenticConfig()), create=MagicMock())
    settings = SimpleNamespace(_agent_factory=factory, agent_max_output_tokens=8192)
    context = enter_context(package)
    token = port.push_bindings(
        tenant_id="south", workspace_id="workspace", subject="issuer|south", bindings={}
    )
    try:
        builder = import_module(package + ".core.agents.builder")
        with pytest.raises(ServiceUnavailableException) as error:
            builder.build_agent(
                name=stage, model="anthropic:ambient", output_type=str, instructions="", settings=settings
            )
        assert error.value.code == "KNOWLEDGE_MODEL_SCOPE_MISMATCH"
    finally:
        port.reset_bindings(token)
    token = port.push_bindings(
        tenant_id="north", workspace_id="workspace", subject="issuer|north", bindings={}
    )
    try:
        with pytest.raises(ServiceUnavailableException) as error:
            builder.build_agent(
                name=stage, model="anthropic:ambient", output_type=str, instructions="", settings=settings
            )
        assert error.value.code == "KNOWLEDGE_MODEL_BINDING_REQUIRED"
        factory.create.assert_not_called()
    finally:
        port.reset_bindings(token)
        context.var.reset(context.token)


async def test_concurrent_tenant_bindings_are_isolated_and_inherited_scopes_expire(domain):
    package, role, _, port = domain
    ready = asyncio.Event()
    release = asyncio.Event()
    observed = []

    async def request(tenant):
        context = enter_context(package, tenant, "issuer|" + tenant)
        model = TestModel(custom_output_text=tenant)
        token = port.push_bindings(
            tenant_id=tenant,
            workspace_id="workspace",
            subject="issuer|" + tenant,
            bindings={role: port.ModelBinding(model, {}, "openai", "chat")},
        )
        try:
            await asyncio.sleep(0)
            observed.append(port.binding_for(role).model)
            assert port.binding_for(role).model is model
            if tenant == "north":

                async def inherited():
                    ready.set()
                    await release.wait()
                    with pytest.raises(ServiceUnavailableException) as error:
                        port.binding_for(role)
                    assert error.value.code == "KNOWLEDGE_MODEL_SCOPE_CLOSED"

                child = asyncio.create_task(inherited())
                await ready.wait()
        finally:
            port.reset_bindings(token)
            context.var.reset(context.token)
        if tenant == "north":
            release.set()
            await child

    await asyncio.gather(request("north"), request("south"))
    assert observed[0] is not observed[1]
    assert port.binding_for(role) is None


async def test_selected_native_models_run_on_the_one_context_factory_without_mutating_settings(domain):
    from pyfly.agentic.factory import AgentFactory
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    package, role, stage, port = domain
    context = ApplicationContext(
        Config(
            {"pyfly": {"agentic": {"enabled": True, "default-model": "test", "plugin-auto-discover": False}}}
        )
    )
    await context.start()
    settings = SimpleNamespace(_agent_factory=context.get_bean(AgentFactory), agent_max_output_tokens=8192)
    try:
        for tenant in ("north", "south"):
            native_context = enter_context(package, tenant, "issuer|" + tenant)
            model = TestModel(custom_output_text=tenant + " selected connection")
            token = port.push_bindings(
                tenant_id=tenant,
                workspace_id="workspace",
                subject="issuer|" + tenant,
                bindings={role: port.ModelBinding(model, {"max_tokens": 160}, "openai", "chat")},
            )
            try:
                agent = import_module(package + ".core.agents.builder").build_agent(
                    name=stage,
                    model="anthropic:ambient-cloud",
                    output_type=str,
                    instructions="Return evidence",
                    settings=settings,
                )
                assert (await agent.run("Synthetic input")).output == tenant + " selected connection"
            finally:
                port.reset_bindings(token)
                native_context.var.reset(native_context.token)
        assert settings.agent_max_output_tokens == 8192
        assert set(vars(settings)) == {"_agent_factory", "agent_max_output_tokens"}
    finally:
        await context.stop()


async def test_document_codeact_uses_the_borrowed_native_connection_and_options_in_worker_thread():
    from flycanon.core.agents.model_bindings import ModelBinding, push_bindings, reset_bindings
    from flycanon.core.services.query.rlm_answer_service import RLMAnswerService
    from pydantic_ai.messages import ModelResponse, ToolCallPart
    from pydantic_ai.models.function import FunctionModel

    observed = []

    def respond(messages, info):
        observed.append(info.model_settings)
        return ModelResponse(parts=[ToolCallPart("python", {"code": "print(42)"}, "owned-call")])

    model = FunctionModel(respond)
    legacy = MagicMock()
    legacy.fork.side_effect = AssertionError("The private deployment provider must not run")
    factory = SimpleNamespace(
        runtime=SimpleNamespace(config=AgenticConfig()),
        create=MagicMock(return_value=SimpleNamespace(agent=SimpleNamespace(model=model))),
    )
    service = object.__new__(RLMAnswerService)
    service._client = legacy
    service._settings = SimpleNamespace(_agent_factory=factory)
    native = enter_context("flycanon")
    token = push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={
            "documents.rlm": ModelBinding(
                model, {"temperature": 0.15, "max_tokens": 88}, "openai", "responses"
            )
        },
    )
    try:

        def run():
            client = service._request_client()
            return client.chat_raw(
                [{"role": "user", "content": "facts?"}], "Use evidence", [{"name": "python"}], max_tokens=1500
            )

        result = await asyncio.to_thread(run)
        assert result["content"][0]["id"] == "owned-call"
        assert observed[0] == {"temperature": 0.15, "max_tokens": 88}
        legacy.fork.assert_not_called()
    finally:
        reset_bindings(token)
        native.var.reset(native.token)


async def test_document_embedding_binding_matches_the_persisted_space_and_never_uses_ambient_client():
    from flycanon.core.agents.model_bindings import EmbeddingBinding, push_bindings, reset_bindings
    from flycanon.core.services.embeddings.embedding_service import EmbeddingService
    from flycanon.core.services.embeddings.embedding_sets import EmbeddingSetBinding, bind_embedding_set
    from pyfly.agentic.embeddings import BaseEmbedder

    class Selected(BaseEmbedder):
        async def _embed_batch(self, texts, **kwargs):
            return [[0.25, 0.75] for _ in texts]

    selected = Selected(model="owned-embedding", dimensions=2)
    ambient = SimpleNamespace(embed=MagicMock(side_effect=AssertionError("Ambient credentials must not run")))
    service = EmbeddingService(embedder=ambient, model="openai:owned-embedding", dimensions=2)
    native = enter_context("flycanon")
    try:
        for space, succeeds in (("existing-set", True), ("different-set", False)):
            token = push_bindings(
                tenant_id="north",
                workspace_id="workspace",
                subject="issuer|north",
                bindings={},
                embeddings={
                    "documents.embedding": EmbeddingBinding(selected, "openai:owned-embedding", 2, 2, space)
                },
            )
            try:
                with bind_embedding_set(EmbeddingSetBinding("existing-set", "openai", "owned-embedding", 2)):
                    if succeeds:
                        assert await service.embed(["facts"]) == [[0.25, 0.75]]
                    else:
                        with pytest.raises(ServiceUnavailableException) as error:
                            await service.embed(["facts"])
                        assert error.value.code == "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED"
            finally:
                reset_bindings(token)
        assert not selected._closed
    finally:
        native.var.reset(native.token)
        await selected.aclose()


async def test_structured_embedding_binding_preserves_dimensions_and_rejects_unqualified_space():
    from flyquery.core.agents.model_bindings import EmbeddingBinding, push_bindings, reset_bindings
    from flyquery.core.services.retrieval.embedder import FireflyEmbedder
    from pyfly.agentic.embeddings import BaseEmbedder

    class Selected(BaseEmbedder):
        async def _embed_batch(self, texts, **kwargs):
            return [[0.25, 0.75] for _ in texts]

    selected = Selected(model="owned-embedding", dimensions=2)
    ambient = SimpleNamespace(
        model="owned-embedding",
        embed_one=MagicMock(side_effect=AssertionError("Ambient credentials must not run")),
    )
    service = FireflyEmbedder(
        inner=ambient,
        target_dim=4,
        native_dim=2,
        embedding_model="openai:owned-embedding",
        space_id="qualified-profile",
    )
    native = enter_context("flyquery")
    try:
        for dimensions, space, succeeds in (
            (2, "qualified-profile", True),
            (3, "qualified-profile", False),
            (2, "new-provider-profile", False),
        ):
            token = push_bindings(
                tenant_id="north",
                workspace_id="workspace",
                subject="issuer|north",
                bindings={},
                embeddings={
                    "structured.embedding": EmbeddingBinding(
                        selected, "openai:owned-embedding", dimensions, 4, space
                    )
                },
            )
            try:
                if succeeds:
                    assert await service.embed("facts") == [0.25, 0.75, 0.0, 0.0]
                else:
                    with pytest.raises(ServiceUnavailableException) as error:
                        await service.embed("facts")
                    assert error.value.code == "KNOWLEDGE_EMBEDDING_REINDEX_REQUIRED"
            finally:
                reset_bindings(token)
        assert not selected._closed
    finally:
        native.var.reset(native.token)
        await selected.aclose()


@pytest.mark.parametrize("package", ["flycanon", "flyquery"])
@pytest.mark.parametrize("vector", [[0.0, 0.0], [float("nan"), 1.0], [float("inf"), 1.0], [True, 1.0]])
async def test_selected_embedding_rejects_invalid_vectors_before_publication(package, vector):
    from contextlib import nullcontext
    from unittest.mock import AsyncMock

    port = import_module(package + ".core.agents.model_bindings")
    selected = SimpleNamespace(
        model="selected",
        dimensions=2,
        embed=AsyncMock(return_value=SimpleNamespace(embeddings=[vector])),
        embed_one=AsyncMock(return_value=vector),
    )
    role = "documents.embedding" if package == "flycanon" else "structured.embedding"
    scope = enter_context(package)
    token = port.push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={},
        embeddings={role: port.EmbeddingBinding(selected, "openai:selected", 2, 2, "existing-set")},
    )
    try:
        if package == "flycanon":
            from flycanon.core.services.embeddings.embedding_service import EmbeddingError, EmbeddingService
            from flycanon.core.services.embeddings.embedding_sets import (
                EmbeddingSetBinding,
                bind_embedding_set,
            )

            service = EmbeddingService(embedder=None, model="openai:selected", dimensions=2)
            indexed = bind_embedding_set(EmbeddingSetBinding("existing-set", "openai", "selected", 2))
            expected = EmbeddingError
        else:
            from flyquery.core.services.retrieval.embedder import FireflyEmbedder

            service = FireflyEmbedder(
                inner=None,
                target_dim=2,
                native_dim=2,
                embedding_model="openai:selected",
                space_id="existing-set",
            )
            indexed = nullcontext()
            expected = ServiceUnavailableException
        with indexed, pytest.raises(expected):
            await service.embed(["facts"] if package == "flycanon" else "facts")
    finally:
        port.reset_bindings(token)
        scope.var.reset(scope.token)


async def test_product_missing_connection_fails_before_original_ingestion():
    from flycanon.core.services.sources.intake_service import IntakeService

    from koinon.knowledge.adapters import NativeDomains

    intake = SimpleNamespace(submit=MagicMock(side_effect=AssertionError("Original intake must not run")))
    container = SimpleNamespace(
        contains_type=lambda kind: kind is IntakeService,
        registered_types=lambda: [],
        resolve=lambda kind: intake,
    )
    with pytest.raises(ServiceUnavailableException) as error:
        await NativeDomains(container).ingest_document(
            tenant_id="north",
            workspace_id="workspace",
            actor="issuer|north",
            filename="facts.txt",
            content=b"facts",
            source_catalog_id="source",
        )
    assert error.value.code == "KNOWLEDGE_CONNECTION_REQUIRED"
    intake.submit.assert_not_called()


async def test_product_resolver_keeps_native_connections_alive_until_original_call_finishes():
    from contextlib import asynccontextmanager

    from flycanon.core.agents.model_bindings import ModelBinding, binding_for
    from flycanon.interfaces.dtos.query import SearchResponse
    from pyfly.container import Container
    from pyfly.cqrs import DefaultQueryBus

    from koinon.knowledge.adapters import NativeDomains
    from koinon.knowledge.model_bindings import DomainConnections, KnowledgeConnectionResolver

    model = TestModel()
    events = []

    class Resolver(KnowledgeConnectionResolver):
        @asynccontextmanager
        async def resolve(self, **scope):
            assert scope == {
                "domain": "canon",
                "tenant_id": "north",
                "workspace_id": "workspace",
                "subject": "issuer|north",
                "purpose": "search",
                "roles": ("documents.embedding",),
                "catalog_workspace_id": None,
            }
            events.append("open")
            try:
                yield DomainConnections({"documents.answer": ModelBinding(model, {}, "openai", "chat")}, {})
            finally:
                events.append("close")

    async def search(message):
        assert events == ["open"]
        await asyncio.sleep(0)
        assert binding_for("documents.answer").model is model
        events.append("original completed")
        return SearchResponse(hits=[], elapsed_ms=1)

    container = Container()
    container.register_instance(Resolver, Resolver())
    container.bind(KnowledgeConnectionResolver, Resolver)
    container.register_instance(DefaultQueryBus, SimpleNamespace(query=search))
    result = await NativeDomains(container).search(
        tenant_id="north",
        workspace_id="workspace",
        actor="issuer|north",
        source_ids=["source"],
        question="facts",
        limit=1,
        answer=False,
    )
    assert result["hits"] == []
    assert events == ["open", "original completed", "close"]
    assert binding_for("documents.answer") is None


async def test_reset_from_inherited_task_cannot_expire_the_parent_connection(domain):
    package, role, _, port = domain
    native = enter_context(package)
    model = TestModel()
    token = port.push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={role: port.ModelBinding(model, {}, "openai", "chat")},
    )
    try:

        async def inherited():
            with pytest.raises(ValueError):
                port.reset_bindings(token)

        await asyncio.create_task(inherited())
        assert port.binding_for(role).model is model
    finally:
        port.reset_bindings(token)
        native.var.reset(native.token)


async def test_product_does_not_accept_an_optional_scope_or_silent_null_embeddings():
    from flycanon.core.agents.model_bindings import push_bindings, reset_bindings
    from flycanon.core.services.sources.intake_service import IntakeService
    from flyquery.core.services.retrieval.embedder import NullEmbedder

    from koinon.knowledge.adapters import NativeDomains

    container = SimpleNamespace(contains_type=lambda kind: kind is IntakeService, registered_types=lambda: [])
    token = push_bindings(
        tenant_id="north", workspace_id="workspace", subject="issuer|north", bindings={}, required=False
    )
    try:
        with pytest.raises(ServiceUnavailableException) as error:
            await NativeDomains(container).ingest_document(
                tenant_id="north",
                workspace_id="workspace",
                actor="issuer|north",
                filename="facts.txt",
                content=b"facts",
                source_catalog_id="source",
            )
        assert error.value.code == "KNOWLEDGE_MODEL_SCOPE_REQUIRED"
    finally:
        reset_bindings(token)
    from flyquery.core.agents.model_bindings import push_bindings as push_structured
    from flyquery.core.agents.model_bindings import reset_bindings as reset_structured

    native = enter_context("flyquery")
    token = push_structured(tenant_id="north", workspace_id="workspace", subject="issuer|north", bindings={})
    try:
        with pytest.raises(ServiceUnavailableException) as error:
            await NullEmbedder().embed("facts")
        assert error.value.code == "KNOWLEDGE_EMBEDDING_BINDING_REQUIRED"
    finally:
        reset_structured(token)
        native.var.reset(native.token)


async def test_stage_limits_reject_incompatible_reasoning_options_before_native_calls(domain):
    package, role, stage, port = domain
    native = enter_context(package)
    model = TestModel()
    factory = SimpleNamespace(runtime=SimpleNamespace(config=AgenticConfig()), create=MagicMock())
    settings = SimpleNamespace(_agent_factory=factory, agent_max_output_tokens=8192)
    token = port.push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={
            role: port.ModelBinding(
                model, {"max_tokens": 4096, "openai_reasoning_effort": "medium"}, "openai", "responses"
            )
        },
    )
    try:
        with pytest.raises(ServiceUnavailableException) as error:
            import_module(package + ".core.agents.builder").build_agent(
                name=stage,
                model="unused:ambient",
                output_type=str,
                instructions="",
                settings=settings,
                max_output_tokens=512,
            )
        assert error.value.code == "KNOWLEDGE_MODEL_BUDGET_INCOMPATIBLE"
        factory.create.assert_not_called()
    finally:
        port.reset_bindings(token)
        native.var.reset(native.token)


def test_product_boot_does_not_construct_ambient_document_or_structured_provider_clients(monkeypatch):
    from unittest.mock import MagicMock

    from flycanon.config import CanonSettings
    from flycanon.core.services.embeddings.embedding_service import EmbeddingRegistry
    from flyquery.config import FlyquerySettings
    from flyquery.core.services.retrieval.embedder import build_embedder

    document_constructor = MagicMock(side_effect=AssertionError("No ambient document client at product boot"))
    structured_constructor = MagicMock(
        side_effect=AssertionError("No ambient structured client at product boot")
    )
    monkeypatch.setattr(
        "flycanon.core.services.embeddings.embedding_service._build_embedder", document_constructor
    )
    monkeypatch.setattr("flyquery.core.services.retrieval.embedder._construct_inner", structured_constructor)
    documents, structured = CanonSettings(), FlyquerySettings()
    documents._require_model_bindings = structured._require_model_bindings = True
    registry = EmbeddingRegistry(settings=documents)
    assert registry.default.model == documents.embedding_model
    assert build_embedder(structured).dimensions == structured.embedding_dimensions
    document_constructor.assert_not_called()
    structured_constructor.assert_not_called()


def test_product_rlm_boot_is_provider_free_and_unconfigured_use_is_actionable(monkeypatch):
    from flycanon.config import CanonSettings
    from flycanon.core.configuration import CanonCoreConfiguration

    factory = SimpleNamespace(
        runtime=SimpleNamespace(config=AgenticConfig()),
        create=MagicMock(side_effect=AssertionError("No default model inference")),
    )
    legacy = MagicMock(side_effect=AssertionError("No private cloud connection at product boot"))
    monkeypatch.setattr("flycanon.core.configuration.build_rlm_client", legacy)
    settings = CanonSettings()
    settings._require_model_bindings = True
    client = CanonCoreConfiguration().rlm_chat_client(settings, factory)
    with pytest.raises(ServiceUnavailableException) as error:
        client.fork()
    assert error.value.code == "KNOWLEDGE_MODEL_BINDING_REQUIRED"
    legacy.assert_not_called()
    factory.create.assert_not_called()


async def test_selected_primary_model_does_not_become_the_deployment_fallback():
    from unittest.mock import AsyncMock

    from flycanon.config import CanonSettings
    from flycanon.core.agents.model_bindings import ModelBinding, push_bindings, reset_bindings
    from flycanon.core.services.query.answer_service import AnswerOutput, AnswerService
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel

    selected = FunctionModel(
        lambda messages, info: ModelResponse(parts=[TextPart("selected")]), model_name="gpt-4o"
    )
    output = AnswerOutput(answer="Selected primary", citation_chunk_ids=[], no_answer=False)
    factory = SimpleNamespace(
        runtime=SimpleNamespace(config=AgenticConfig()),
        create=MagicMock(
            return_value=SimpleNamespace(run=AsyncMock(return_value=SimpleNamespace(output=output)))
        ),
    )
    settings = CanonSettings(answer_model="anthropic:private-primary", answer_fallback_model="openai:gpt-4o")
    settings._agent_factory = factory
    service = object.__new__(AnswerService)
    service._settings = settings
    service._default_model, service._fallback_model = settings.answer_model, settings.answer_fallback_model
    native = enter_context("flycanon")
    token = push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={"documents.answer": ModelBinding(selected, {"max_tokens": 512}, "openai", "chat")},
    )
    try:
        assert await service._call_model("Instructions", "Facts", settings.answer_model) is output
        assert factory.create.call_args.kwargs["model"] is selected
    finally:
        reset_bindings(token)
        native.var.reset(native.token)


async def test_native_bound_model_does_not_acquire_deployment_temperature_when_native_options_omit_it(domain):
    from pydantic_ai.messages import ModelResponse, TextPart
    from pydantic_ai.models.function import FunctionModel
    from pyfly.agentic.factory import AgentFactory
    from pyfly.context import ApplicationContext
    from pyfly.core import Config

    package, role, stage, port = domain
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "agentic": {
                        "enabled": True,
                        "default-model": "test",
                        "default-temperature": 0.75,
                        "plugin-auto-discover": False,
                    }
                }
            }
        )
    )
    await context.start()
    captured = []

    def respond(messages, info):
        captured.append(info.model_settings)
        return ModelResponse(parts=[TextPart("Native response")])

    model = FunctionModel(respond)
    factory = context.get_bean(AgentFactory)
    settings = SimpleNamespace(_agent_factory=factory, agent_max_output_tokens=8192)
    native = enter_context(package)
    token = port.push_bindings(
        tenant_id="north",
        workspace_id="workspace",
        subject="issuer|north",
        bindings={role: port.ModelBinding(model, {"max_tokens": 128}, "openai", "responses")},
    )
    try:
        agent = import_module(package + ".core.agents.builder").build_agent(
            name=stage,
            model="unused:ambient",
            output_type=str,
            instructions="Native options",
            settings=settings,
        )
        assert (await agent.run("Synthetic input")).output == "Native response"
        assert "temperature" not in captured[0]
        assert factory.runtime.config.default_temperature == 0.75
    finally:
        port.reset_bindings(token)
        native.var.reset(native.token)
        await context.stop()
