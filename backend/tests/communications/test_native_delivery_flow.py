# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

from pyfly.data.transaction import current_unit_of_work
from pyfly.notifications import EmailStatus, NotificationResult
from pyfly.security.context import SecurityContext
from test_email_invitations import ACTOR, PERSON, draft
from test_email_invitations import email_context as email_context

from koinon.communications.delivery import EmailDispatcher
from koinon.communications.identity import CommunicationIdentityBindings
from koinon.communications.invitations import EmailInvitationService
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.repositories import OutboxRepository, RecipientIdentityRepository
from koinon.communications.submission import EmailSubmission


def owned_transport(context, outcome=EmailStatus.SENT):
    messages = []

    async def send(message):
        assert current_unit_of_work("primary") is None
        assert message.body_html and message.body_text
        assert "Powered by koinon" in message.body_html and "Firefly Software Foundation" in message.body_text
        messages.append(message)
        return NotificationResult(message.id, "owned-inert", outcome)

    context.get_bean(EmailDispatcher).container = SimpleNamespace(
        resolve=lambda kind: SimpleNamespace(send=send)
    )
    return messages


async def test_native_invitation_claim_revalidates_and_submits_actual_html_text_once(email_context):
    context, _ = email_context
    service = context.get_bean(EmailInvitationService)
    invitation = await service.create(ACTOR, "north", await draft(context), "native-delivery")
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    row = await context.get_bean(OutboxRepository).find_by_id(ticket.id)
    assert row.status == "sent", row.failure_code
    assert len(messages) == 1 and messages[0].id == ticket.id
    assert invitation.id in messages[0].body_text and "north" in messages[0].subject
    assert await state.claim("owned-next") is None


async def test_revocation_after_render_before_sending_fences_the_queued_message(email_context, monkeypatch):
    context, _ = email_context
    invitations = context.get_bean(EmailInvitationService)
    invitation = await invitations.create(ACTOR, "north", await draft(context), "revoke-during-render")
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    original = state.write_payload

    async def revoke_after_freeze(*args):
        result = await original(*args)
        await invitations.revoke(ACTOR, "north", invitation.id)
        return result

    monkeypatch.setattr(state, "write_payload", revoke_after_freeze)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert not messages
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "cancelled"


async def test_pending_provider_operation_becomes_unknown_and_is_not_sent_again(email_context):
    context, _ = email_context
    await context.get_bean(EmailInvitationService).create(
        ACTOR, "north", await draft(context), "provider-pending"
    )
    messages = owned_transport(context, EmailStatus.QUEUED)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert len(messages) == 1
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "unknown"
    assert await state.claim("owned-next") is None


async def test_only_fresh_verified_native_login_binds_immutable_directory_identity(email_context):
    context, _ = email_context
    login = SecurityContext(user_id="person", attributes={"iss": "https://issuer.test", "sub": "person"})
    await context.get_bean(CommunicationIdentityBindings).observe_login(login)
    rows = await context.get_bean(RecipientIdentityRepository).find_all(subject=PERSON)
    assert len(rows) == 1 and rows[0].external_subject == "person"
    assert rows[0].provider_id == "provider" and rows[0].provider_revision == 1


async def test_unverified_delivery_address_does_not_block_native_login_or_invent_a_binding(email_context):
    context, directory = email_context
    directory.raw["emailVerified"] = False
    login = SecurityContext(user_id="person", attributes={"iss": "https://issuer.test", "sub": "person"})
    await context.get_bean(CommunicationIdentityBindings).observe_login(login)
    assert not await context.get_bean(RecipientIdentityRepository).find_all(subject=PERSON)


async def test_known_failed_invitation_can_be_explicitly_retried_but_unknown_cannot(email_context):
    from datetime import UTC, datetime, timedelta

    from koinon.communications.administration import CommunicationsAdministration
    from koinon.communications.repositories import EmailInvitationRepository

    context, _ = email_context
    invitation = await context.get_bean(EmailInvitationService).create(
        ACTOR, "north", await draft(context), "known-failed"
    )
    messages = owned_transport(context, EmailStatus.FAILED)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    repository = context.get_bean(EmailInvitationRepository)
    row = await repository.find_by_id(invitation.id)
    row.last_queued_at = datetime.now(UTC) - timedelta(hours=1)
    await repository.save(row)
    admin = context.get_bean(CommunicationsAdministration)
    assert (await admin.delivery(ACTOR, "north", ticket.id)).can_retry
    next_delivery = await admin.retry(ACTOR, "north", ticket.id)
    assert next_delivery.id != ticket.id and next_delivery.status == "queued"
    assert not (await admin.delivery(ACTOR, "north", ticket.id)).can_retry
    assert len(messages) == 1
