# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pyfly.notifications import EmailStatus
from test_bootstrap_welcome import ISSUER, OID, TID, observation, pending
from test_email_invitations import email_context as email_context
from test_native_delivery_flow import owned_transport
from test_operator_contacts import contacts

from koinon.communications.bootstrap_contacts import BootstrapContacts
from koinon.communications.contact_dtos import OperatorContactInput
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.recovery import WelcomeRecoveryService
from koinon.communications.recovery_dtos import WelcomeRecoveryInput
from koinon.communications.recovery_repository import WelcomeRecoveryRepository
from koinon.communications.repositories import OutboxRepository
from koinon.communications.submission import EmailSubmission


async def prepared(context, *, correlate=False):
    await pending(context)
    original = await context.get_bean(BootstrapContacts).admit(observation())
    state = context.get_bean(CommunicationOutbox)
    sent = owned_transport(context, EmailStatus.UNKNOWN)
    if correlate:
        from types import SimpleNamespace

        from pyfly.notifications import NotificationResult
        from pyfly.notifications.services import DefaultEmailService

        from koinon.communications.delivery import EmailDispatcher

        dispatcher = context.get_bean(EmailDispatcher)
        capture = dispatcher.container.resolve(DefaultEmailService).send

        async def correlated_send(message):
            await capture(message)
            return NotificationResult(
                message.id, "azure-communication-email", EmailStatus.UNKNOWN, provider_id=message.id
            )

        dispatcher.container = SimpleNamespace(resolve=lambda kind: SimpleNamespace(send=correlated_send))
    await context.get_bean(EmailSubmission).execute(await state.claim("original-worker"))
    assert len(sent) == 1
    operator = await contacts(context)
    now = datetime.now(UTC)
    target = await operator.provision(
        OperatorContactInput(
            tenant_id="north",
            identity=dict(
                kind="entra", issuer=ISSUER, client_id="client", external_tenant_id=TID, external_subject=OID
            ),
            email="admin@example.test",
            display_name="Initial administrator",
            source="microsoft_graph_v1",
            account_enabled=True,
            observed_at=now,
            expires_at=now + timedelta(hours=2),
        )
    )
    for kind in (WelcomeRecoveryRepository, WelcomeRecoveryService):
        context.register_bean(kind)
    service = context.get_bean(WelcomeRecoveryService)
    context.get_bean(EmailSubmission).welcome_recovery = service
    return service, target, await context.get_bean(OutboxRepository).find_by_id(original.event_id)


def request(original, target, **changes):
    value = dict(
        expected_generation=original.generation,
        contact_id=target.id,
        expected_contact_revision=target.revision,
        reason="recipient_reported_not_received",
        acknowledge_possible_duplicate=True,
    )
    value.update(changes)
    return WelcomeRecoveryInput.model_validate(value)


async def test_explicit_prelogin_recovery_creates_new_delivery_without_replaying_original(email_context):
    context, directory = email_context
    service, target, original = await prepared(context)
    before = (original.status, original.attempt_count, original.payload_hash, original.provider_reference)
    key = str(uuid4())
    admitted = await service.operator_recover(original.id, request(original, target), key)
    again = await service.operator_recover(original.id, request(original, target), key)
    assert again.delivery_id == admitted.delivery_id != original.id
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    await context.get_bean(EmailSubmission).execute(await state.claim("recovery-worker"))
    assert len(messages) == 1 and messages[0].to == ["admin@example.test"]
    assert messages[0].id == admitted.delivery_id and "welcome" in messages[0].subject.lower()
    saved = await context.get_bean(OutboxRepository).find_by_id(original.id)
    assert (saved.status, saved.attempt_count, saved.payload_hash, saved.provider_reference) == before
    assert await state.claim("no-auto-recovery") is None
    assert target.canonical_subject is None and directory.reads == 0


async def test_recovery_key_conflict_and_duplicate_acknowledgment_are_enforced(email_context):
    from pydantic import ValidationError
    from pyfly.kernel import ConflictException

    context, _ = email_context
    service, target, original = await prepared(context)
    with pytest.raises(ValidationError):
        request(original, target, acknowledge_possible_duplicate=False)
    key = str(uuid4())
    await service.operator_recover(original.id, request(original, target), key)
    with pytest.raises(ConflictException):
        await service.operator_recover(
            original.id, request(original, target, expected_contact_revision=2), key
        )


async def test_contact_change_after_render_cancels_new_delivery_and_keeps_original_unknown(
    email_context, monkeypatch
):
    context, _ = email_context
    service, target, original = await prepared(context)
    admitted = await service.operator_recover(original.id, request(original, target), str(uuid4()))
    state = context.get_bean(CommunicationOutbox)
    write = state.write_payload

    async def revoke(*args):
        result = await write(*args)
        await context.get_bean(type(service.operator_contacts)).revoke(target.id, target.revision)
        return result

    monkeypatch.setattr(state, "write_payload", revoke)
    messages = owned_transport(context)
    await context.get_bean(EmailSubmission).execute(await state.claim("revoked-recovery"))
    assert messages == []
    repo = context.get_bean(OutboxRepository)
    assert (await repo.find_by_id(admitted.delivery_id)).status == "cancelled"
    assert (await repo.find_by_id(original.id)).status == "unknown"


@pytest.mark.parametrize(
    "field,value",
    [("expected_generation", 999), ("expected_contact_revision", 999), ("contact_id", "missing")],
)
async def test_stale_or_unknown_contact_cannot_queue_manual_recovery(email_context, field, value):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied

    context, _ = email_context
    service, target, original = await prepared(context)
    with pytest.raises((AccessDenied, ConflictException)):
        await service.operator_recover(original.id, request(original, target, **{field: value}), str(uuid4()))
    assert not await service.records.find_all()
    assert len(await context.get_bean(OutboxRepository).find_all(kind="welcome")) == 1


async def test_prelogin_recovery_requires_current_pending_grant_and_no_canonical_principal(
    email_context, monkeypatch
):
    from koinon.catalog.errors import AccessDenied

    context, _ = email_context
    service, target, original = await prepared(context)

    async def expired():
        return target.expires_at + timedelta(days=1)

    monkeypatch.setattr(service.outbox, "clock", expired)
    with pytest.raises(AccessDenied):
        await service.operator_recover(original.id, request(original, target), str(uuid4()))
    assert not await service.records.find_all()
    assert target.canonical_subject is None


async def test_exact_manual_request_replay_survives_generation_change_without_requeue(email_context):
    context, _ = email_context
    service, target, original = await prepared(context)
    body = request(original, target)
    key = str(uuid4())
    first = await service.operator_recover(original.id, body, key)
    original.generation += 1
    await context.get_bean(OutboxRepository).save(original)
    again = await service.operator_recover(original.id, body, key)
    assert again.delivery_id == first.delivery_id and len(await service.records.find_all()) == 1


async def test_ordinary_admin_cannot_use_prelogin_operator_path_or_foreign_tenant(email_context):
    from test_email_invitations import ACTOR, PERSON

    from koinon.catalog.errors import AccessDenied

    context, _ = email_context
    service, target, original = await prepared(context)
    for actor, tenant in [(ACTOR, "north"), (ACTOR, "south"), (PERSON, "north")]:
        with pytest.raises(AccessDenied):
            await service.recover(actor, tenant, original.id, request(original, target), str(uuid4()))
    assert not await service.records.find_all()


async def bound_prepared(context):
    from pyfly.data.relational.sqlalchemy import transactional
    from test_email_invitations import ACTOR
    from test_operator_contacts import bind
    from test_operator_contacts import observation as signed_observation

    from koinon.communications.welcome import WelcomeAdmissions

    operator = await contacts(context)
    target = await operator.provision(signed_observation())
    await bind(operator)

    @transactional
    async def automatic():
        return await context.get_bean(WelcomeAdmissions).admit(ACTOR, "north")

    admission = await automatic()
    for kind in (WelcomeRecoveryRepository, WelcomeRecoveryService):
        context.register_bean(kind)
    service = context.get_bean(WelcomeRecoveryService)
    context.get_bean(EmailSubmission).welcome_recovery = service
    return service, target, await context.get_bean(OutboxRepository).find_by_id(admission.event_id)


async def test_current_org_admin_can_explicitly_recover_bound_target_and_origin_revocation_fences_send(
    email_context,
):
    from test_email_invitations import ACTOR

    from koinon.catalog.repositories import MembershipRepository

    context, _ = email_context
    service, target, original = await bound_prepared(context)
    contact, reason = await service.recovery_options(ACTOR, "north", original.id)
    assert contact.id == target.id and reason is None
    admitted = await service.recover(ACTOR, "north", original.id, request(original, target), str(uuid4()))
    member = (await context.get_bean(MembershipRepository).find_all(tenant_id="north", subject=ACTOR))[0]
    member.active = False
    await context.get_bean(MembershipRepository).save(member)
    messages = owned_transport(context)
    await context.get_bean(EmailSubmission).execute(
        await context.get_bean(CommunicationOutbox).claim("revoked-admin")
    )
    assert messages == []
    assert (await context.get_bean(OutboxRepository).find_by_id(admitted.delivery_id)).status in {
        "suppressed",
        "cancelled",
    }


@pytest.mark.parametrize("ceiling", ["workspace_ids", "asset_ids", "resource_ids", "missing_scope"])
async def test_limited_pat_cannot_admit_organization_welcome_recovery(email_context, ceiling):
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder
    from test_email_invitations import ACTOR

    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.entities import PersonalToken
    from koinon.tokens.repositories import PersonalTokenRepository

    context, _ = email_context
    service, target, original = await bound_prepared(context)
    token = PersonalToken(
        id=uuid4().hex,
        subject=ACTOR,
        tenant_id="north",
        name="Owned test token",
        token_hash="f" * 64,
        prefix="owned-fixture",
        scopes=["members:write"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    if ceiling == "missing_scope":
        token.scopes = ["profile:read"]
    else:
        setattr(token, ceiling, [])
    await context.get_bean(PersonalTokenRepository).save(token)
    with (
        SecurityContextHolder.using(
            SecurityContext(
                user_id="admin",
                attributes={"iss": "https://issuer.test", "sub": "admin", "koinon_token_id": token.id},
            )
        ),
        pytest.raises(AccessDenied),
    ):
        await service.recover(ACTOR, "north", original.id, request(original, target), str(uuid4()))
    assert not await service.records.find_all()


async def test_recovery_options_bounds_contact_ambiguity_read(email_context, monkeypatch):
    from pyfly.data.relational.sqlalchemy import transactional
    from sqlalchemy import event
    from test_email_invitations import ACTOR

    from koinon.communications.contact_entities import OperatorContactRecord

    context, _ = email_context
    service, target, original = await bound_prepared(context)
    records = service.operator_contacts.contacts
    selected = await records.find_by_id(target.id)
    for number in range(8):
        values = {
            column.name: getattr(selected, column.name)
            for column in OperatorContactRecord.__table__.columns
        }
        values.update(id=str(uuid4()), identity_key=f"ambiguous-{number}")
        await records.save(OperatorContactRecord(**values))
    statements = []

    @transactional(read_only=True)
    async def observe():
        connection = await records._require_session().connection()
        def capture(conn, cursor, statement, parameters, context, executemany):
            if "koinon_operator_delivery_contacts" in statement and "canonical_subject" in statement:
                statements.append((statement, parameters))
        event.listen(connection.sync_connection.engine, "before_cursor_execute", capture)
        try:
            return await service.recovery_options(ACTOR, "north", original.id)
        finally:
            event.remove(connection.sync_connection.engine, "before_cursor_execute", capture)

    async def forbidden(*args, **kwargs):
        raise AssertionError("Ambiguous contacts must not invoke recipient resolution")
    monkeypatch.setattr(service, "_recipient", forbidden)
    contact, reason = await observe()
    assert contact is None and reason == "WELCOME_RECOVERY_CONTACT_UNAVAILABLE"
    assert len(statements) == 1
    assert "LIMIT" in statements[0][0] and 2 in statements[0][1]
