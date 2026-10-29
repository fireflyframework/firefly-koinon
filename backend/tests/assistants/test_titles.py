# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock, Mock

import pytest
from pydantic_ai.models.test import TestModel
from pyfly.kernel import ConflictException
from test_service import assistants as assistants
from test_service import configured


async def test_title_uses_exact_borrowed_agent_model_without_another_client_and_is_revision_bound(
    assistants, monkeypatch
):
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.model_bindings import BorrowedModel, bind_model
    from koinon.assistants.probe import ProviderProbe
    from koinon.assistants.title_service import TitleService

    service, context = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[
                {"id": "connection", "status": "passed", "message": "Controlled"},
                {"id": "models", "status": "passed", "message": "Discovered"},
            ]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    thread = await service.create_thread("issuer|viewer", "north", {})
    model = TestModel(
        custom_output_text='{"title":"Quarterly order totals"}', profile={"supports_json_schema_output": True}
    )
    requests = []
    original_request = TestModel.request

    async def recorded(self, messages, *args, **kwargs):
        requests.append(str(messages))
        return await original_request(self, messages, *args, **kwargs)

    monkeypatch.setattr(TestModel, "request", recorded)
    build = Mock(side_effect=AssertionError("A matching borrowed native model must be reused"))
    monkeypatch.setattr(ModelFactory, "build_with_secret", build)

    from koinon.assistants.queue import AssistantQueue

    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Add all order values", "client_request_id": "title-1"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("title-worker")
    await queue.append(run.id, "title-worker", "message_delta", {"text": "The total is 12."})
    await queue.finish(run.id, "title-worker")
    binding = BorrowedModel(
        model,
        {"max_tokens": 768},
        "ollama",
        "chat",
        "native",
        agent_id=agent["id"],
        agent_revision=agent["revision"],
        provider_id=provider["id"],
        provider_revision=provider["revision"],
    )
    with bind_model("north", "issuer|viewer", binding):
        proposal = await context.get_bean(TitleService).propose(
            "issuer|viewer", "north", thread["id"], agent["id"], expected_revision=1
        )
    assert proposal.model_dump() == {"title": "Quarterly order totals", "based_on_revision": 1}
    assert "Add all order values" in str(requests)
    assert "The total is 12" not in str(requests)
    build.assert_not_called()
    with pytest.raises(ConflictException):
        await context.get_bean(TitleService).propose(
            "issuer|viewer", "north", thread["id"], agent["id"], expected_revision=999
        )


async def test_automatic_title_is_optional_revision_bound_and_skips_manual_titles(assistants, monkeypatch):
    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.history.service import ChatHistoryService
    from koinon.assistants.queue import AssistantQueue
    from koinon.assistants.title_dtos import TitleSuggestion
    from koinon.assistants.title_service import TitleService

    service, context = assistants
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Order totals", "client_request_id": "automatic-title"},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("title-worker")
    executor = context.get_bean(AssistantExecutor)
    titles = context.get_bean(TitleService)
    history = context.get_bean(ChatHistoryService)
    propose = AsyncMock(return_value=TitleSuggestion(title="Order totals", based_on_revision=1))
    apply = AsyncMock(return_value=True)
    monkeypatch.setattr(titles, "propose", propose)
    monkeypatch.setattr(history, "apply_generated_title", apply)
    await executor.suggest_title(run.id, "title-worker", timeout=1)
    apply.assert_awaited_once_with(
        "issuer|viewer", "north", thread["id"], "Order totals", expected_revision=1
    )
    propose.side_effect = RuntimeError("Controlled optional title failure")
    await executor.suggest_title(run.id, "title-worker", timeout=1)
    assert apply.await_count == 1
    propose.side_effect = None
    propose.reset_mock()
    await history.patch_thread(
        "issuer|viewer", "north", thread["id"], {"title": "My manual title", "expected_revision": 1}
    )
    await executor.suggest_title(run.id, "title-worker", timeout=1)
    propose.assert_not_awaited()
    await executor.suggest_title(run.id, "title-worker", timeout=0)
    propose.assert_not_awaited()


async def test_expired_private_file_evidence_is_not_sent_to_the_title_model(assistants, monkeypatch):
    from types import SimpleNamespace

    from pyfly.agentic.models import ModelFactory
    from test_attachment_admission import attachment

    from koinon.assistants.probe import ProviderProbe
    from koinon.assistants.queue import AssistantQueue
    from koinon.assistants.title_service import TitleService
    from koinon.catalog.errors import AccessDenied

    service, context = assistants
    monkeypatch.setattr(
        ProviderProbe,
        "check",
        AsyncMock(
            return_value=[{"id": "connection", "status": "passed"}, {"id": "models", "status": "passed"}]
        ),
    )
    provider, agent = await configured(service)
    await service.validate_provider("issuer|admin", "north", provider["id"])
    thread = await service.create_thread("issuer|viewer", "north", {})
    service.attachments = SimpleNamespace(
        validate_selection=AsyncMock(return_value=(attachment(),)),
        pin_selection=AsyncMock(),
        for_run=AsyncMock(return_value=(attachment(),)),
    )
    await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {
            "agent_id": agent["id"],
            "message": "Title my private file discussion",
            "client_request_id": "expired-title",
            "attachment_ids": ["file-one"],
        },
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("title-worker")
    await queue.append(run.id, "title-worker", "message_delta", {"text": "Private evidence that expired."})
    await queue.finish(run.id, "title-worker")
    service.attachments.for_run.side_effect = AccessDenied("The private file expired")
    build = Mock(side_effect=AssertionError("Expired private text must not enter a model client"))
    monkeypatch.setattr(ModelFactory, "build_with_secret", build)
    with pytest.raises(AccessDenied):
        await context.get_bean(TitleService).propose(
            "issuer|viewer", "north", thread["id"], agent["id"], expected_revision=1
        )
    build.assert_not_called()


def title_protocol_fixture(factory, *, kind, mode, profile=None):
    """Fake authority/repositories, with real public factory and SDK model execution only."""
    from types import SimpleNamespace

    from pydantic_ai.messages import ModelResponse, TextPart, ToolCallPart
    from pydantic_ai.models.function import FunctionModel
    from pyfly.agentic.models import ModelFactory

    from koinon.assistants.connections import ConnectionResolver
    from koinon.assistants.settings import AssistantSettings
    from koinon.assistants.title_service import TitleService

    requests = []

    def answer(messages, info):
        requests.append(info)
        part = (
            TextPart('{"title":"Offline title"}')
            if info.model_request_parameters.output_mode == "native"
            else ToolCallPart(info.output_tools[0].name, {"title": "Offline title"}, "actual-title-call")
        )
        return ModelResponse(parts=[part])

    model = FunctionModel(
        answer, profile={"supports_tools": True, "supports_json_schema_output": True, **(profile or {})}
    )
    agent = SimpleNamespace(
        id="agent",
        revision=1,
        provider_id="provider",
        enabled=True,
        model_id="qwen2.5:3b" if kind == "ollama" else "gpt-4o",
        scope={},
        model_options={} if mode is None else {"output_mode": mode},
    )
    provider = SimpleNamespace(
        id="provider",
        revision=1,
        validated_revision=1,
        kind=kind,
        api="chat",
        base_url="http://127.0.0.1:11434/v1",
        model_ids=[agent.model_id],
        enabled=True,
        secret_ciphertext=None if kind == "ollama" else "fixture-ciphertext",
        checks=[{"id": "connection", "status": "passed"}, {"id": "models", "status": "passed"}],
    )
    agents, providers = object(), object()

    async def scoped(repository, *_args):
        return agent if repository is agents else provider

    resolver = ConnectionResolver(AssistantSettings(allowed_provider_hosts=["127.0.0.1"]), ModelFactory())
    assistants = SimpleNamespace(
        agents=agents,
        providers=providers,
        scoped=scoped,
        thread=AsyncMock(return_value=SimpleNamespace(revision=1, scope={})),
        validate_scope=AsyncMock(return_value={}),
        owned_run=AsyncMock(),
        runs=SimpleNamespace(
            recent_title_runs=AsyncMock(
                return_value=[SimpleNamespace(id="run", scope={}, user_message_id="message")]
            )
        ),
        message_repository=SimpleNamespace(
            find_by_id=AsyncMock(
                return_value=SimpleNamespace(role="user", text="An offline conversation excerpt")
            )
        ),
        configuration_service=SimpleNamespace(connections=resolver),
        secrets=SimpleNamespace(decrypt=Mock(return_value="fixture-key")),
    )
    models = SimpleNamespace(build_with_secret=Mock(return_value=model))
    service = TitleService(assistants, models, SimpleNamespace(resolve=lambda _type: factory))
    return SimpleNamespace(
        service=service, agent=agent, provider=provider, model=model, models=models, requests=requests
    )


@pytest.fixture
async def title_factory():
    from pyfly.agentic.config import AgenticConfig
    from pyfly.agentic.runtime import AgenticRuntime

    async with AgenticRuntime(AgenticConfig(default_model="test", plugin_auto_discover=False)) as runtime:
        yield runtime.agent_factory


@pytest.mark.parametrize(
    "kind,choice,expected",
    [
        ("ollama", "default", "tool"),
        ("openai", "native", "native"),
        ("ollama", None, "native"),
        ("openai", None, "tool"),
    ],
)
async def test_title_honors_explicit_protocol_and_preserves_legacy_unset(
    title_factory, kind, choice, expected
):
    fixture = title_protocol_fixture(title_factory, kind=kind, mode=choice)
    result = await fixture.service.propose("actor", "tenant", "thread", "agent", expected_revision=1)
    assert result.title == "Offline title"
    assert len(fixture.requests) == 1
    assert fixture.requests[0].model_request_parameters.output_mode == expected
    assert fixture.requests[0].model_settings["max_tokens"] == 64
    assert "output_mode" not in fixture.requests[0].model_settings
    fixture.models.build_with_secret.assert_called_once()


@pytest.mark.parametrize(
    "kind,configured,borrowed",
    [
        ("ollama", "native", "default"),
        ("openai", "default", "native"),
    ],
)
async def test_title_reuses_exact_borrowed_mode_instead_of_rederiving_provider_or_agent(
    title_factory, kind, configured, borrowed
):
    from koinon.assistants.model_bindings import BorrowedModel, bind_model

    fixture = title_protocol_fixture(title_factory, kind=kind, mode=configured)
    binding = BorrowedModel(
        fixture.model,
        {},
        kind,
        "chat",
        borrowed,
        agent_id="agent",
        agent_revision=1,
        provider_id="provider",
        provider_revision=1,
    )
    with bind_model("tenant", "actor", binding):
        await fixture.service.propose("actor", "tenant", "thread", "agent", expected_revision=1)
    assert len(fixture.requests) == 1
    assert fixture.requests[0].model_request_parameters.output_mode == (
        "native" if borrowed == "native" else "tool"
    )
    fixture.models.build_with_secret.assert_not_called()


@pytest.mark.parametrize("mode", ["default", "native"])
@pytest.mark.parametrize("borrowed", [False, True])
async def test_title_rejects_unsupported_actual_mode_before_factory_or_model_request(
    title_factory, monkeypatch, mode, borrowed
):
    from contextlib import nullcontext

    from pyfly.kernel import ServiceUnavailableException

    from koinon.assistants.model_bindings import BorrowedModel, bind_model

    fixture = title_protocol_fixture(
        title_factory,
        kind="ollama",
        mode=mode,
        profile={"supports_tools": mode != "default", "supports_json_schema_output": mode != "native"},
    )
    create = Mock(side_effect=AssertionError("Unsupported modes must fail before agent construction"))
    monkeypatch.setattr(title_factory, "create", create)
    binding = BorrowedModel(
        fixture.model,
        {},
        "ollama",
        "chat",
        mode,
        agent_id="agent",
        agent_revision=1,
        provider_id="provider",
        provider_revision=1,
    )
    with (
        bind_model("tenant", "actor", binding) if borrowed else nullcontext(),
        pytest.raises(ServiceUnavailableException) as raised,
    ):
        await fixture.service.propose("actor", "tenant", "thread", "agent", expected_revision=1)
    assert raised.value.code == "AGENT_MODEL_OUTPUT_MODE_UNSUPPORTED"
    assert fixture.requests == []
    create.assert_not_called()


async def test_default_title_keeps_bare_type_and_honors_sdk_profile_default(title_factory, monkeypatch):
    from koinon.assistants.title_dtos import TitleText

    fixture = title_protocol_fixture(
        title_factory, kind="ollama", mode="default", profile={"default_structured_output_mode": "native"}
    )
    original = title_factory.create
    create = Mock(side_effect=original)
    monkeypatch.setattr(title_factory, "create", create)
    await fixture.service.propose("actor", "tenant", "thread", "agent", expected_revision=1)
    assert create.call_args.kwargs["output_type"] is TitleText
    assert fixture.requests[0].model_request_parameters.output_mode == "native"
