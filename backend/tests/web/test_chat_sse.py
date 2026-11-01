# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""HTTP streaming uses durable, owner-authorized event cursors."""

import json

from conftest import ISSUER, bearer

from koinon.answers.receipts import legacy_notice


async def seed(context, *, terminal=True):
    from chat_seed import seed as seed_chat

    return await seed_chat(context, issuer=ISSUER, terminal=terminal)


def test_legacy_sse_masks_unsealed_text_and_retains_cursors_and_security_headers(client):
    run = client.portal.call(seed, client.native_app.state.context)
    url = f"/api/v1/tenants/north/chat/runs/{run}/events"
    response = client.get(url, headers=bearer())
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.text.count("id: ") == 2
    first_data = next(
        line.removeprefix("data: ") for line in response.text.splitlines() if line.startswith("data: ")
    )
    assert json.loads(first_data)["text"] == legacy_notice("en")
    assert "Árbol" not in response.text and "Second line" not in response.text
    resumed = client.get(url, headers={**bearer(), "Last-Event-ID": "2"})
    assert "id: 3" in resumed.text and "id: 1" not in resumed.text
    assert "message_delta" not in resumed.text
    assert client.get(url, headers={**bearer(), "Last-Event-ID": "3"}).text == ""


def test_sealed_unicode_response_is_released_once_and_last_event_cursor_does_not_drop_it(client):
    from koinon.answers.dtos import EvidenceAnswerPlan
    from koinon.assistants.queue import AssistantQueue
    from koinon.assistants.service import AssistantService
    from koinon.assistants.settings import AssistantSettings

    context = client.native_app.state.context

    async def publish():
        context.get_bean(AssistantSettings).allowed_provider_hosts = ["127.0.0.1"]
        service = context.get_bean(AssistantService)
        provider = await service.save_provider(
            f"{ISSUER}|admin",
            "north",
            {
                "name": "Controlled",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["unused"],
            },
        )
        agent = await service.save_agent(
            f"{ISSUER}|admin",
            "north",
            {"name": "Controlled", "provider_id": provider["id"], "model_id": "unused"},
        )
        thread = await service.create_thread(f"{ISSUER}|admin", "north", {})
        await service.submit(
            f"{ISSUER}|admin",
            "north",
            thread["id"],
            {"agent_id": agent["id"], "message": "What is known?", "client_request_id": "sealed-unicode"},
        )
        queue = context.get_bean(AssistantQueue)
        run = await queue.claim("sealed-http")
        receipt = await queue.release_answer(
            run.id,
            "sealed-http",
            EvidenceAnswerPlan(outcome="insufficient_evidence"),
            "es",
            refusal_code="KNOWLEDGE_ONLY",
        )
        await queue.finish(run.id, "sealed-http")
        return (
            run.id,
            receipt.publication_sequence,
            (await service.message_repository.find_by_id(run.message_id)).text,
        )

    run, sequence, text = client.portal.call(publish)
    assert "organización" in text
    url = f"/api/v1/tenants/north/chat/runs/{run}/events"

    def deltas(response):
        return [
            json.loads(next(line[6:] for line in frame.splitlines() if line.startswith("data: ")))["text"]
            for frame in response.text.split("\n\n")
            if "event: message_delta\n" in frame
        ]

    response = client.get(url, headers=bearer())
    assert response.status_code == 200 and deltas(response) == [text]
    resumed_before = client.get(url, headers={**bearer(), "Last-Event-ID": str(sequence - 1)})
    assert deltas(resumed_before) == [text] and "event: completed" in resumed_before.text
    resumed_after = client.get(url, headers={**bearer(), "Last-Event-ID": str(sequence)})
    assert deltas(resumed_after) == [] and "event: completed" in resumed_after.text


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

    from koinon.assistants.audit import AnswerAudits
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
            context.get_bean(AssistantService),
            context.get_bean(ChatHistoryService),
            context.get_bean(AnswerAudits),
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

    from koinon.assistants.audit import AnswerAudits
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
            context.get_bean(AssistantService),
            context.get_bean(ChatHistoryService),
            context.get_bean(AnswerAudits),
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
        fresh = await anext(response.body_iterator)
        assert "id: 4" in fresh and legacy_notice("en") in fresh
        assert "FRESH_ATTEMPT" not in fresh and "OLD_ATTEMPT_FACT" not in fresh
        await response.body_iterator.aclose()

    client.portal.call(verify)
