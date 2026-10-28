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
