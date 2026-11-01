# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException
from pyfly.security.context import SecurityContext
from test_email_invitations import ACTOR
from test_email_invitations import email_context as email_context
from test_native_delivery_flow import owned_transport

from koinon.communications.contact_dtos import OperatorContactInput
from koinon.communications.contact_repository import OperatorContactRepository
from koinon.communications.events import CommunicationEvents
from koinon.communications.operator_contacts import OperatorContacts
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.repositories import OutboxRepository
from koinon.communications.submission import EmailSubmission


def observation(**changes):
    now = datetime.now(UTC)
    values = dict(
        tenant_id="north",
        identity=dict(
            kind="keycloak", issuer="https://issuer.test", client_id="client", external_subject="admin"
        ),
        email="approved@example.test",
        display_name="Approved operator",
        source="keycloak_admin",
        account_enabled=True,
        observed_at=now,
        expires_at=now + timedelta(hours=2),
    )
    values.update(changes)
    return OperatorContactInput.model_validate(values)


async def contacts(context):
    for kind in (OperatorContactRepository, OperatorContacts):
        context.register_bean(kind)
    value = context.get_bean(OperatorContacts)
    context.get_bean(EmailSubmission).operator_contacts = value
    return value


async def bind(service, *, subject="admin", **claims):
    await service.observe_login(
        SecurityContext(
            user_id=subject, attributes=dict(iss="https://issuer.test", sub=subject, aud="client", **claims)
        )
    )


async def security(context, owner=ACTOR):
    @transactional
    async def create():
        await context.get_bean(CommunicationEvents).security_changed(
            owner, owner, "north", "token_created", "synthetic-token", "Synthetic account notice"
        )

    await create()


async def test_operator_contact_sends_new_account_notice_without_directory_and_does_not_create_access(
    email_context,
):
    context, directory = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    assert row.canonical_subject is None
    await bind(service)
    await security(context)
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert [message.to for message in messages] == [["approved@example.test"]]
    assert directory.reads == 0
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "sent"


@pytest.mark.parametrize(
    "claims", [{"aud": "other"}, {"koinon_token_id": "token"}, {"iss": "https://other.test"}]
)
async def test_untrusted_login_cannot_bind_an_operator_contact(email_context, claims):
    context, _ = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    attributes = dict(iss="https://issuer.test", sub="admin", aud="client")
    attributes.update(claims)
    await service.observe_login(SecurityContext(user_id="admin", attributes=attributes))
    assert (await context.get_bean(OperatorContactRepository).find_by_id(row.id)).canonical_subject is None


async def test_new_operator_diagnostic_is_idempotent_throttled_and_does_not_replay_unknown(email_context):
    from pyfly.notifications import EmailStatus

    context, directory = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    await bind(service)
    operation = str(uuid4())
    first = await service.diagnostic(row.id, operation)
    assert (await service.diagnostic(row.id, operation))["delivery_id"] == first["delivery_id"]
    with pytest.raises(ConflictException, match="diagnostic"):
        await service.diagnostic(row.id, str(uuid4()))
    messages = owned_transport(context, EmailStatus.UNKNOWN)
    state = context.get_bean(CommunicationOutbox)
    await context.get_bean(EmailSubmission).execute(await state.claim("owned-worker"))
    assert len(messages) == 1 and "diagnostic" in messages[0].body_text.lower()
    assert (await service.diagnostic(row.id, operation))["status"] == "unknown"
    assert await state.claim("owned-again") is None
    assert directory.reads == 0


async def test_revocation_after_render_cancels_without_transmission(email_context, monkeypatch):
    context, _ = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    await bind(service)
    await security(context)
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    original = state.write_payload

    async def revoke(*args):
        result = await original(*args)
        await service.revoke(row.id, 1)
        return result

    monkeypatch.setattr(state, "write_payload", revoke)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert not messages
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "cancelled"


async def test_unknown_external_account_state_is_preserved_and_unbound_contacts_are_not_ready(email_context):
    from koinon.catalog.errors import AccessDenied

    context, _ = email_context
    service = await contacts(context)
    value = observation(account_enabled=None)
    row = await service.provision(value)
    assert value.account_enabled is None
    status = await service.status(row.id)
    assert status["recipient_state"] == "pending_signed_login" and not status["can_queue_diagnostic"]
    assert "approved@example.test" not in str(status)
    with pytest.raises(AccessDenied):
        await service.diagnostic(row.id, str(uuid4()))
    await bind(service)
    assert (await service.status(row.id))["can_queue_diagnostic"]


async def test_expiry_and_current_admin_revocation_make_a_bound_contact_ineligible(
    email_context, monkeypatch
):
    from koinon.catalog.repositories import MembershipRepository

    context, _ = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    await bind(service)
    members = context.get_bean(MembershipRepository)
    admin = (await members.find_all(tenant_id="north", subject=ACTOR))[0]
    admin.active = False
    await members.save(admin)
    status = await service.status(row.id)
    assert status["recipient_state"] == "eligible"
    assert not status["administrative_eligible"] and not status["can_queue_diagnostic"]

    async def expired():
        return row.expires_at + timedelta(seconds=1)

    monkeypatch.setattr(service.outbox, "clock", expired)
    assert (await service.status(row.id))["recipient_state"] == "expired"


async def test_contact_renewal_is_cas_and_post_render_revision_change_fences_the_old_payload(
    email_context, monkeypatch
):
    context, _ = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    await bind(service)
    await security(context)
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    original = state.write_payload

    async def renew(*args):
        result = await original(*args)
        changed = await service.renew(row.id, 1, observation(email="new-approved@example.test"))
        assert changed.revision == 2
        with pytest.raises(ConflictException):
            await service.renew(row.id, 1, observation())
        return result

    monkeypatch.setattr(state, "write_payload", renew)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert not messages
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "cancelled"


async def test_directory_identity_observer_uses_the_approved_contact_without_graph(email_context):
    from koinon.communications.identity import CommunicationIdentityBindings

    context, directory = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    observer = context.get_bean(CommunicationIdentityBindings)
    observer.operator_contacts = service
    login = SecurityContext(
        user_id="admin", attributes=dict(iss="https://issuer.test", sub="admin", aud="client")
    )
    await observer.observe_login(login)
    await observer.observe_login(login)
    assert (await service.status(row.id))["recipient_state"] == "eligible"
    assert directory.reads == 0


async def test_entra_reuses_only_actual_signed_bootstrap_activation_never_oid_as_subject(email_context):
    from test_bootstrap_welcome import ISSUER, OID, TID, activate, pending

    from koinon.bootstrap.repositories import BootstrapGrantRepository

    context, _ = email_context
    context.register_bean(BootstrapGrantRepository)
    await pending(context)
    await activate(context)
    service = await contacts(context)
    service.bootstrap_grants = context.get_bean(BootstrapGrantRepository)
    row = await service.provision(
        observation(
            identity=dict(
                kind="entra", issuer=ISSUER, client_id="client", external_tenant_id=TID, external_subject=OID
            ),
            source="microsoft_graph_v1",
            account_enabled=None,
        )
    )
    assert row.canonical_subject == ISSUER + "|real-pairwise"
    assert not row.canonical_subject.endswith(OID)
    assert (await service.status(row.id))["recipient_state"] == "eligible"


async def test_google_contact_requires_exact_broker_and_external_identity(email_context):
    context, _ = email_context
    service = await contacts(context)
    row = await service.provision(
        observation(
            identity=dict(
                kind="google_workspace",
                issuer="https://issuer.test",
                client_id="client",
                external_subject="google-immutable",
                broker_alias="workspace",
                hosted_domains=["example.test"],
            ),
            source="google_admin",
        )
    )
    await bind(
        service,
        koinon_identity_provider="workspace",
        koinon_external_subject="wrong",
        koinon_google_hd="example.test",
    )
    assert (await service.status(row.id))["recipient_state"] == "pending_signed_login"
    await bind(
        service,
        koinon_identity_provider="workspace",
        koinon_external_subject="google-immutable",
        koinon_google_hd="example.test",
    )
    assert (await service.status(row.id))["recipient_state"] == "eligible"


async def test_native_operator_cli_uses_the_owner_registry_and_only_queues_a_new_diagnostic(email_context):
    import importlib.util
    from pathlib import Path

    context, _ = email_context
    service = await contacts(context)
    spec = importlib.util.spec_from_file_location(
        "operator_contacts_cli_flow", Path(__file__).parents[3] / "deploy/communications.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    args = cli.arguments(["provision", "--contacts-file", "protected-input.json"])
    admitted = await cli.execute(context, args, [observation()])
    identifier = admitted["contacts"][0]["contact_id"]
    pending = await cli.execute(context, cli.arguments(["status", "--contact-id", identifier]))
    assert pending["recipient_state"] == "pending_signed_login"
    await bind(service)
    operation = str(uuid4())
    queued = await cli.execute(
        context, cli.arguments(["diagnostic", "--contact-id", identifier, "--operation-id", operation])
    )
    assert queued["status"] == "queued"
    event = await context.get_bean(OutboxRepository).find_by_id(queued["delivery_id"])
    assert event.attempt_count == 0 and event.owner_subject == ACTOR
    assert event.event_json["subtype"] == "delivery_diagnostic"


async def test_durable_contact_survives_daily_weekly_monthly_windows_without_automatic_extension(
    email_context, monkeypatch
):
    context, _ = email_context
    service = await contacts(context)
    value = observation(expires_at=datetime.now(UTC) + timedelta(days=90))
    row = await service.provision(value)
    await bind(service)
    original_expiry = row.expires_at

    async def later():
        return value.observed_at + timedelta(days=40)

    monkeypatch.setattr(service.outbox, "clock", later)
    status = await service.status(row.id)
    assert status["recipient_state"] == "eligible" and status["expiry_state"] == "current"
    await bind(service)
    assert (
        await context.get_bean(OperatorContactRepository).find_by_id(row.id)
    ).expires_at == original_expiry

    async def warning():
        return original_expiry - timedelta(days=10)

    monkeypatch.setattr(service.outbox, "clock", warning)
    assert (await service.status(row.id))["expiry_state"] == "expiring"

    async def expired():
        return original_expiry + timedelta(seconds=1)

    monkeypatch.setattr(service.outbox, "clock", expired)
    assert (await service.status(row.id))["recipient_state"] == "expired"


async def test_stale_operator_observation_is_rejected_even_for_durable_authorization(email_context):
    context, _ = email_context
    service = await contacts(context)
    with pytest.raises(ValueError, match="fresh observation"):
        await service.provision(
            observation(
                observed_at=datetime.now(UTC) - timedelta(hours=1),
                expires_at=datetime.now(UTC) + timedelta(days=365),
            )
        )
    service.settings.operator_contact_max_lifetime_days = 30
    with pytest.raises(ValueError, match="installation policy"):
        await service.provision(observation(expires_at=datetime.now(UTC) + timedelta(days=90)))


async def test_security_notice_survives_role_loss_but_new_diagnostic_requires_current_admin(email_context):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository

    context, _ = email_context
    service = await contacts(context)
    row = await service.provision(observation())
    await bind(service)
    members = context.get_bean(MembershipRepository)
    admin = (await members.find_all(tenant_id="north", subject=ACTOR))[0]
    admin.active = False
    await members.save(admin)
    await security(context)
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    await context.get_bean(EmailSubmission).execute(await state.claim("owned-worker"))
    assert len(messages) == 1
    with pytest.raises(AccessDenied):
        await service.diagnostic(row.id, str(uuid4()))


def test_contact_lifetime_configuration_has_real_typed_bounds():
    from pyfly.core import Config

    from koinon.communications.settings import CommunicationsSettings

    assert CommunicationsSettings().operator_contact_max_lifetime_days == 365
    configured = Config({"koinon": {"communications": {"operator_contact_max_lifetime_days": 90}}}).bind(
        CommunicationsSettings
    )
    assert configured.operator_contact_max_lifetime_days == 90
    for value in (0, 3651, True):
        with pytest.raises(ValueError):
            CommunicationsSettings(operator_contact_max_lifetime_days=value)
