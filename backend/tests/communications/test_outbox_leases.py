# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from test_membership_events import communications as communications

from koinon.catalog.service import CatalogService
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.repositories import OutboxRepository


async def pending(context):
    await context.get_bean(CatalogService).create_member(
        "https://issuer.test|admin", "north", subject="https://issuer.test|person", role="viewer"
    )
    return context.get_bean(CommunicationOutbox)


async def expire(context, ticket):
    repository = context.get_bean(OutboxRepository)
    row = await repository.find_by_id(ticket.id)
    row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    await repository.save(row)


async def test_expired_preparation_is_fenced_and_cannot_begin_or_complete_another_attempt(communications):
    queue = await pending(communications)
    first = await queue.claim("worker-one")
    assert first is not None and await queue.claim("worker-two") is None
    await expire(communications, first)
    second = await queue.claim("worker-two")
    assert second.id == first.id and second.generation > first.generation
    assert not await queue.write_payload(first, "ciphertext", "0" * 64)
    assert not await queue.begin_send(first)
    assert not await queue.complete(first, "sent")
    assert await queue.write_payload(second, "ciphertext", "0" * 64)
    assert await queue.begin_send(second)
    assert await queue.complete(second, "sent")
    assert await queue.claim("worker-three") is None


async def test_expired_sending_is_unknown_and_never_automatically_replayed(communications):
    queue = await pending(communications)
    ticket = await queue.claim("worker-one")
    assert await queue.write_payload(ticket, "ciphertext", "0" * 64)
    assert await queue.begin_send(ticket)
    await expire(communications, ticket)
    assert await queue.claim("worker-two") is None
    row = await communications.get_bean(OutboxRepository).find_by_id(ticket.id)
    assert row.status == "unknown" and row.failure_code == "SEND_OUTCOME_UNKNOWN"
    assert not await queue.complete(ticket, "sent")
    assert await queue.claim("worker-three") is None


async def test_payload_and_operation_identity_cannot_be_replaced_or_completed_by_foreign_owner(
    communications,
):
    queue = await pending(communications)
    ticket = await queue.claim("worker-one")
    assert await queue.write_payload(ticket, "ciphertext-one", "0" * 64)
    assert not await queue.write_payload(ticket, "ciphertext-two", "1" * 64)
    assert not await queue.begin_send(replace(ticket, owner="worker-two"))
    assert await queue.begin_send(ticket)
    assert not await queue.complete(replace(ticket, owner="worker-two"), "sent")
    assert await queue.complete(ticket, "unknown", failure_code="SEND_OUTCOME_UNKNOWN")


async def test_exhausted_deferred_preparation_becomes_terminal_without_resubmission(communications):
    queue = await pending(communications)
    ticket = await queue.claim("worker-one")
    repository = communications.get_bean(OutboxRepository)
    row = await repository.find_by_id(ticket.id)
    row.status, row.attempt_count = "deferred", queue.settings.max_attempts
    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    row.lease_until = row.lease_owner = None
    await repository.save(row)
    assert await queue.claim("worker-two") is None
    row = await repository.find_by_id(ticket.id)
    assert row.status == "failed" and row.failure_code == "PREPARATION_ATTEMPTS_EXHAUSTED"
