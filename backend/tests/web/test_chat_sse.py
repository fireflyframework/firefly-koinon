# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""HTTP streaming uses durable, owner-authorized event cursors."""

import json

from conftest import ISSUER, bearer


async def seed(context, *, terminal=True):
    from koinon.assistants.entities import AgentConfiguration, ChatEvent, ChatMessage, ChatRun, Provider
    from koinon.assistants.repositories import (
        AgentRepository,
        ChatEventRepository,
        ChatMessageRepository,
        ChatRunRepository,
        ProviderRepository,
    )
    from koinon.assistants.service import AssistantService

    provider = await context.get_bean(ProviderRepository).save(
        Provider(
            id="stream-provider",
            tenant_id="north",
            name="Controlled stream",
            kind="ollama",
            base_url="http://127.0.0.1:11434/v1",
            model_ids=["controlled"],
        )
    )
    agent = await context.get_bean(AgentRepository).save(
        AgentConfiguration(
            id="stream-agent",
            tenant_id="north",
            provider_id=provider.id,
            name="Controlled stream",
            model_id="controlled",
        )
    )
    thread = await context.get_bean(AssistantService).create_thread(f"{ISSUER}|admin", "north", {})
    messages = context.get_bean(ChatMessageRepository)
    user = await messages.save(
        ChatMessage(id="stream-user", thread_id=thread["id"], role="user", text="Question")
    )
    answer = await messages.save(
        ChatMessage(
            id="stream-answer",
            thread_id=thread["id"],
            role="assistant",
            text="Árbol\nSecond line",
            status="completed" if terminal else "running",
        )
    )
    run = await context.get_bean(ChatRunRepository).save(
        ChatRun(
            id="stream-run",
            tenant_id="north",
            thread_id=thread["id"],
            user_message_id=user.id,
            message_id=answer.id,
            agent_id=agent.id,
            agent_revision=1,
            provider_revision=1,
            client_request_id="controlled-stream",
            payload_hash="0" * 64,
            status="completed" if terminal else "running",
            sequence=3 if terminal else 1,
        )
    )
    events = [("message_delta", {"text": "Árbol\nSecond line"})]
    if terminal:
        events.extend(
            [
                ("message_metadata", {"answer_policy": {"outcome": "grounded"}}),
                ("completed", {"status": "completed"}),
            ]
        )
    for sequence, (kind, data) in enumerate(events, 1):
        await context.get_bean(ChatEventRepository).save(
            ChatEvent(id=f"stream-event-{sequence}", run_id=run.id, sequence=sequence, type=kind, data=data)
        )
    return run.id


def test_sse_replays_only_events_after_cursor_and_retains_security_headers(client):
    run = client.portal.call(seed, client.native_app.state.context)
    url = f"/api/v1/tenants/north/chat/runs/{run}/events"
    response = client.get(url, headers=bearer())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.text.count("id: ") == 3
    first_data = next(
        line.removeprefix("data: ") for line in response.text.splitlines() if line.startswith("data: ")
    )
    assert json.loads(first_data)["text"] == "Árbol\nSecond line"
    resumed = client.get(url, headers={**bearer(), "Last-Event-ID": "2"})
    assert "id: 3" in resumed.text and "id: 1" not in resumed.text
    assert "message_delta" not in resumed.text
    assert client.get(url, headers={**bearer(), "Last-Event-ID": "3"}).text == ""


def test_sse_denies_foreign_owner_scope_and_bad_cursor_before_stream_headers(client):
    run = client.portal.call(seed, client.native_app.state.context)
    url = f"/api/v1/tenants/north/chat/runs/{run}/events"
    for headers, status in (
        ({}, 401),
        (bearer("viewer"), 403),
        ({**bearer(), "Last-Event-ID": "bad\rvalue"}, 400),
        ({**bearer(), "Last-Event-ID": "-1"}, 400),
    ):
        response = client.get(url, headers=headers)
        assert response.status_code == status, response.text
        assert not response.headers.get("content-type", "").startswith("text/event-stream")


def test_closing_stream_preserves_durable_run_and_revocation_stops_further_events(client, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.assistants.controllers import AssistantController
    from koinon.assistants.history.service import ChatHistoryService
    from koinon.assistants.repositories import ChatRunRepository
    from koinon.assistants.service import AssistantService
    from koinon.catalog.repositories import MembershipRepository

    context = client.native_app.state.context
    monkeypatch.setattr(
        "koinon.assistants.controllers.identity_from_request",
        lambda request: SimpleNamespace(subject=f"{ISSUER}|admin"),
    )

    async def verify():
        run = await seed(context, terminal=False)
        from koinon.assistants.entities import ChatEvent
        from koinon.assistants.repositories import ChatEventRepository

        stored = await context.get_bean(ChatRunRepository).find_by_id(run)
        stored.sequence = 2
        await context.get_bean(ChatRunRepository).save(stored)
        await context.get_bean(ChatEventRepository).save(
            ChatEvent(
                id="stream-second-pending",
                run_id=run,
                sequence=2,
                type="message_delta",
                data={"text": "A pending delta must be reauthorized"},
            )
        )
        controller = AssistantController(
            context.get_bean(AssistantService), context.get_bean(ChatHistoryService)
        )
        request = SimpleNamespace(headers={}, is_disconnected=AsyncMock(return_value=False))
        response = await controller.events("north", run, request)
        first = await anext(response.body_iterator)
        assert "message_delta" in first
        await response.body_iterator.aclose()
        stored = await context.get_bean(ChatRunRepository).find_by_id(run)
        assert stored.status == "running" and stored.sequence == 2
        response = await controller.events("north", run, request)
        assert "message_delta" in await anext(response.body_iterator)
        await context.get_bean(MembershipRepository).delete_by_id("admin")
        revoked = await anext(response.body_iterator)
        assert "ACCESS_DENIED" in revoked and "event: failed" in revoked
        await response.body_iterator.aclose()
        assert (await context.get_bean(ChatRunRepository).find_by_id(run)).status == "running"

    client.portal.call(verify)


def test_buffered_old_attempt_delta_is_dropped_when_a_retry_resets_the_message(client, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.assistants.controllers import AssistantController
    from koinon.assistants.entities import ChatEvent
    from koinon.assistants.history.service import ChatHistoryService
    from koinon.assistants.repositories import ChatEventRepository, ChatRunRepository
    from koinon.assistants.service import AssistantService

    context = client.native_app.state.context
    monkeypatch.setattr(
        "koinon.assistants.controllers.identity_from_request",
        lambda request: SimpleNamespace(subject=f"{ISSUER}|admin"),
    )

    async def verify():
        run_id = await seed(context, terminal=False)
        events = context.get_bean(ChatEventRepository)
        runs = context.get_bean(ChatRunRepository)
        run = await runs.find_by_id(run_id)
        run.sequence = 2
        await runs.save(run)
        await events.save(
            ChatEvent(
                id="buffered-old",
                run_id=run_id,
                sequence=2,
                type="message_delta",
                data={"text": "OLD_ATTEMPT_FACT"},
            )
        )
        controller = AssistantController(
            context.get_bean(AssistantService), context.get_bean(ChatHistoryService)
        )
        response = await controller.events(
            "north", run_id, SimpleNamespace(headers={}, is_disconnected=AsyncMock(return_value=False))
        )
        assert "message_delta" in await anext(response.body_iterator)
        await events.save(
            ChatEvent(
                id="new-reset", run_id=run_id, sequence=3, type="message_reset", data={"status": "running"}
            )
        )
        await events.save(
            ChatEvent(
                id="fresh-only",
                run_id=run_id,
                sequence=4,
                type="message_delta",
                data={"text": "FRESH_ATTEMPT"},
            )
        )
        run = await runs.find_by_id(run_id)
        run.sequence = 4
        run.status = "completed"
        await runs.save(run)
        next_event = await anext(response.body_iterator)
        assert "OLD_ATTEMPT_FACT" not in next_event and "message_reset" in next_event
        assert "FRESH_ATTEMPT" in await anext(response.body_iterator)
        await response.body_iterator.aclose()

    client.portal.call(verify)
