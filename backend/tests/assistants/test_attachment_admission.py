# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.lifecycle import timestamp
from koinon.assistants.repositories import ChatMessageRepository, ChatRunRepository
from koinon.catalog.errors import AccessDenied
from koinon.knowledge.attachments.dtos import AttachmentHistorySummary
from koinon.knowledge.attachments.ports import AttachmentRef, ChatAttachmentAccess


def attachment(identifier="file-one", digest="a" * 64):
    return AttachmentRef(
        id=identifier,
        tenant_id="north",
        thread_id="thread",
        subject="issuer|viewer",
        sha256=digest,
        revision=3,
        filename="Notes.md",
        media_type="text/markdown",
        kind="document",
        size_bytes=100,
        expires_at=timestamp() + timedelta(hours=1),
    )


async def request(service):
    _, agent = await configured(service)
    thread = await service.create_thread("issuer|viewer", "north", {})
    return thread["id"], {
        "agent_id": agent["id"],
        "message": "Compare the selected notes",
        "client_request_id": "private-files",
        "attachment_ids": ["file-one"],
    }


async def test_selected_files_are_authorized_before_admission_and_atomically_pinned_to_user_message(
    assistants,
):
    service, context = assistants
    thread, payload = await request(service)
    refs = (attachment(),)
    service.attachments = SimpleNamespace(
        validate_selection=AsyncMock(return_value=refs),
        pin_selection=AsyncMock(),
    )
    first = await service.submit("issuer|viewer", "north", thread, payload)
    service.attachments.validate_selection.assert_awaited_once_with(
        "issuer|viewer",
        "north",
        thread,
        ["file-one"],
    )
    run = await context.get_bean(ChatRunRepository).find_by_id(first["run_id"])
    service.attachments.pin_selection.assert_awaited_once_with(
        "issuer|viewer",
        "north",
        thread,
        refs,
        run_id=run.id,
        message_id=run.user_message_id,
    )
    assert await service.submit("issuer|viewer", "north", thread, payload) == first
    assert service.attachments.pin_selection.await_count == 1
    service.attachments.validate_selection.return_value = (attachment(digest="b" * 64),)
    with pytest.raises(ConflictException) as failure:
        await service.submit("issuer|viewer", "north", thread, payload)
    assert failure.value.code == "IDEMPOTENCY_CONFLICT"


@pytest.mark.parametrize("ids", [["file-one", "file-one"], [""], ["a"] * 11, "file-one"])
async def test_invalid_file_selections_never_create_messages(assistants, ids):
    service, context = assistants
    thread, payload = await request(service)
    with pytest.raises(InvalidRequestException):
        await service.submit("issuer|viewer", "north", thread, {**payload, "attachment_ids": ids})
    assert await context.get_bean(ChatMessageRepository).find_all(thread_id=thread) == []


async def test_absent_attachment_adapter_fails_closed_but_text_only_requests_keep_working(assistants):
    service, context = assistants
    thread, payload = await request(service)
    with pytest.raises(ServiceUnavailableException):
        await service.submit("issuer|viewer", "north", thread, payload)
    assert await context.get_bean(ChatMessageRepository).find_all(thread_id=thread) == []
    assert await service.submit("issuer|viewer", "north", thread, {**payload, "attachment_ids": []})


async def test_native_late_attachment_port_is_resolved_after_service_creation(assistants):
    service, context = assistants
    thread, payload = await request(service)
    assert service.attachments is None
    access = SimpleNamespace(
        validate_selection=AsyncMock(return_value=(attachment(),)),
        pin_selection=AsyncMock(),
    )
    context.container.register_instance(ChatAttachmentAccess, access)
    assert await service.submit("issuer|viewer", "north", thread, payload)
    access.pin_selection.assert_awaited_once()


async def test_failed_atomic_attachment_pin_rolls_back_run_and_both_messages(assistants):
    service, context = assistants
    thread, payload = await request(service)
    service.attachments = SimpleNamespace(
        validate_selection=AsyncMock(return_value=(attachment(),)),
        pin_selection=AsyncMock(side_effect=ConflictException("The selected file changed")),
    )
    with pytest.raises(ConflictException):
        await service.submit("issuer|viewer", "north", thread, payload)
    assert await context.get_bean(ChatRunRepository).find_all(thread_id=thread) == []
    assert await context.get_bean(ChatMessageRepository).find_all(thread_id=thread) == []


async def test_expired_file_blocks_replay_and_retry_but_preserves_owner_history_and_cancellation(assistants):
    service, context = assistants
    thread, payload = await request(service)
    ref = attachment()
    service.attachments = SimpleNamespace(
        validate_selection=AsyncMock(return_value=(ref,)),
        pin_selection=AsyncMock(),
        for_run=AsyncMock(side_effect=AccessDenied("The selected file expired")),
        summaries_for_message=AsyncMock(return_value=()),
    )
    accepted = await service.submit("issuer|viewer", "north", thread, payload)
    run = await context.get_bean(ChatRunRepository).find_by_id(accepted["run_id"])
    summary = AttachmentHistorySummary(
        id=ref.id,
        filename=ref.filename,
        media_type=ref.media_type,
        kind="document",
        size_bytes=ref.size_bytes,
        sha256=ref.sha256,
        revision=ref.revision,
        expires_at=timestamp() - timedelta(seconds=1),
        status="expired",
        available=False,
    )
    service.attachments.summaries_for_message.side_effect = lambda subject, tenant, thread_id, message_id: (
        (summary,) if message_id == run.user_message_id else ()
    )
    with pytest.raises(AccessDenied):
        await service.run_events("issuer|viewer", "north", accepted["run_id"])
    assert (await service.cancel("issuer|viewer", "north", accepted["run_id"]))["status"] == "cancelled"
    with pytest.raises(AccessDenied):
        await service.retry("issuer|viewer", "north", accepted["run_id"])
    history = await service.messages("issuer|viewer", "north", thread)
    assert history[0]["text"] == payload["message"]
    assert history[0]["attachments"] == [summary.model_dump(mode="json")]
    assert service.attachments.for_run.await_count == 2
