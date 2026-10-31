# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import asyncio
from collections.abc import Awaitable, Callable

from koinon_sdk import (
    ChatRun,
    ChatThread,
    ConversationExportInput,
    Export,
    ExportCreate,
    ExportReview,
    KnowledgeScope,
    KoinonClient,
    RunInput,
    Share,
    ShareCreate,
    ShareReview,
    StreamEvent,
    ThreadPatch,
)
from support import connect, required


async def create_conversation(
    client: KoinonClient,
    tenant: str,
    scope: KnowledgeScope,
) -> ChatThread:
    return await client.create_thread(tenant, title="Knowledge question", scope=scope)


async def start_question(
    client: KoinonClient,
    tenant: str,
    thread_id: str,
    scope: KnowledgeScope,
    question: str,
    stable_request_id: str,
) -> ChatRun:
    settings = await client.organization_chat_settings(
        tenant,
        workspace_id=scope.workspace_id,
        project_id=scope.project_id,
    )
    if not settings.can_run or settings.default_agent_id is None:
        raise RuntimeError("An operator must configure the organization's chat agent")
    return await client.submit_run(
        tenant,
        thread_id,
        RunInput(
            agent_id=settings.default_agent_id,
            message=question,
            scope=scope,
            client_request_id=stable_request_id,
            attachment_ids=[],
        ),
    )


async def consume_run(
    client: KoinonClient,
    tenant: str,
    run_id: str,
    checkpoint: Callable[[StreamEvent, str], Awaitable[None]],
    last_processed_id: str | None = None,
    initial_text: str = "",
) -> tuple[str, str, str]:
    partial = initial_text
    async with client.events(tenant, run_id, last_event_id=last_processed_id) as events:
        async for event in events:
            if event.type == "message_reset":
                partial = ""
            elif event.type == "message_delta":
                partial += event.data.text or ""
            await checkpoint(event, partial)
            last_processed_id = event.id
            if event.type in {"completed", "failed", "cancelled"}:
                return last_processed_id, event.type, partial
    raise RuntimeError("Stream ended without a terminal event; reconcile the saved run")


async def move_reviewed_thread(
    client: KoinonClient,
    tenant: str,
    reviewed: ChatThread,
    folder_id: str | None,
    person_confirmed: bool,
) -> ChatThread:
    if not person_confirmed:
        raise ValueError("Review the selected folder and thread first")
    return await client.update_thread(
        tenant,
        reviewed.id,
        ThreadPatch(expected_revision=reviewed.revision, folder_id=folder_id),
    )


async def review_conversation_export(
    client: KoinonClient,
    tenant: str,
    thread_id: str,
    message_ids: list[str],
) -> ExportReview:
    return await client.review_export(
        tenant,
        ConversationExportInput(
            kind="conversation",
            format="markdown",
            thread_id=thread_id,
            message_ids=message_ids,
            include_evidence=True,
        ),
    )


async def create_reviewed_export(
    client: KoinonClient,
    tenant: str,
    reviewed: ExportReview,
    person_confirmed: bool,
) -> Export:
    if not person_confirmed:
        raise ValueError("Display the exact export review and request confirmation")
    return await client.create_export(
        tenant,
        ExportCreate(
            review_id=reviewed.id,
            expected_revision=reviewed.revision,
        ),
    )


async def create_reviewed_share(
    client: KoinonClient,
    tenant: str,
    reviewed: ShareReview,
    person_confirmed: bool,
) -> Share:
    if not person_confirmed:
        raise ValueError("Display the exact recipients and selected messages first")
    return await client.create_share(
        tenant,
        ShareCreate(
            review_id=reviewed.id,
            expected_revision=reviewed.revision,
            recipient_policy=reviewed.recipient_policy,
            expires_in_hours=24,
        ),
    )


async def main() -> None:
    async with connect() as client:
        page = await client.threads(required("KOINON_TENANT_ID"), page=1, page_size=25)
        for thread in page.items:
            print(thread.id, thread.title, thread.revision)


if __name__ == "__main__":
    asyncio.run(main())
