# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared owned chat ledger fixture without pytest conftest imports."""

async def seed(context, *, issuer: str, terminal=True):
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
    thread = await context.get_bean(AssistantService).create_thread(f"{issuer}|admin", "north", {})
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

