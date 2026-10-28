# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import InvalidRequestException
from test_service import assistants as assistants
from test_service import configured

from koinon.assistants.lifecycle import timestamp
from koinon.assistants.queue import AssistantQueue
from koinon.catalog.errors import AccessDenied
from koinon.evidence.ports import ConversationSnapshotPort
from koinon.tokens.repositories import PersonalTokenRepository


async def final_turn(service, context, *, thread=None, private=False, legacy=False):
    _, agent = await configured(service)
    thread = thread or await service.create_thread("issuer|viewer", "north", {})
    accepted = await service.submit(
        "issuer|viewer",
        "north",
        thread["id"],
        {"agent_id": agent["id"], "message": "Question", "client_request_id": str(timestamp())},
    )
    queue = context.get_bean(AssistantQueue)
    run = await queue.claim("snapshot-worker")
    if private:
        await queue.evidence(run.id, "snapshot-worker", "attachment", {"attachments": []}, [])
    await queue.append(run.id, "snapshot-worker", "message_delta", {"text": "Reviewed owner text"})
    if not legacy:
        await queue.policy(run.id, "snapshot-worker", {"outcome": "grounded" if private else "refused"})
    await queue.finish(run.id, "snapshot-worker")
    return thread, run, accepted


async def test_native_snapshot_port_is_owner_scoped_final_and_revision_stable(assistants):
    service, context = assistants
    thread, run, _ = await final_turn(service, context)
    port = context.get_bean(ConversationSnapshotPort)
    snapshot = await port.snapshot(
        "issuer|viewer", "north", thread["id"], [run.message_id, run.user_message_id]
    )
    assert [row.role for row in snapshot.messages] == ["user", "assistant"]
    assert len(snapshot.revision) == 64 and snapshot.source_manifest_complete is True
    assert snapshot == await port.snapshot(
        "issuer|viewer", "north", thread["id"], [run.user_message_id, run.message_id]
    )
    for subject, tenant in (("issuer|other", "north"), ("issuer|outsider", "south")):
        with pytest.raises(AccessDenied):
            await port.snapshot(subject, tenant, thread["id"], [run.message_id])
    with pytest.raises(InvalidRequestException):
        await port.snapshot("issuer|viewer", "north", thread["id"], [run.message_id, run.message_id])
    other, foreign, _ = await final_turn(service, context)
    with pytest.raises(AccessDenied):
        await port.snapshot("issuer|viewer", "north", thread["id"], [foreign.message_id])


async def test_private_derivation_is_transitive_even_without_current_selection_and_legacy_is_incomplete(
    assistants,
):
    service, context = assistants
    thread, private, _ = await final_turn(service, context, private=True)
    _, later, _ = await final_turn(service, context, thread=thread)
    snapshot = await context.get_bean(ConversationSnapshotPort).snapshot(
        "issuer|viewer", "north", thread["id"], [later.message_id]
    )
    assert snapshot.messages[0].private_derived is True
    assert "attachments" not in snapshot.model_dump(mode="json")
    clean, legacy, _ = await final_turn(service, context, legacy=True)
    old = await context.get_bean(ConversationSnapshotPort).snapshot(
        "issuer|viewer", "north", clean["id"], [legacy.message_id]
    )
    assert old.source_manifest_complete is False


async def test_revoked_originating_token_blocks_snapshot_before_delivery(assistants):
    service, context = assistants
    thread, run, _ = await final_turn(service, context)
    run.access_token_id = "originating-token"
    await service.runs.save(run)
    row = SimpleNamespace(
        subject="issuer|viewer",
        tenant_id="north",
        revoked_at=timestamp(),
        expires_at=timestamp() + timedelta(hours=1),
    )
    context.container.register_instance(
        PersonalTokenRepository, SimpleNamespace(find_by_id=AsyncMock(return_value=row))
    )
    from koinon.tokens.authorization import TokenRestriction

    service.catalog.restriction = TokenRestriction(
        context.get_bean(PersonalTokenRepository), service.catalog.catalog_repository
    )
    with pytest.raises(AccessDenied):
        await context.get_bean(ConversationSnapshotPort).snapshot(
            "issuer|viewer", "north", thread["id"], [run.message_id]
        )
