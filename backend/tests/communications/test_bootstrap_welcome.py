# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.notifications import EmailStatus
from test_email_invitations import email_context as email_context
from test_native_delivery_flow import owned_transport

from koinon.bootstrap.entities import BootstrapIdentityGrant
from koinon.bootstrap.repositories import BootstrapGrantRepository
from koinon.communications.bootstrap_contacts import BootstrapContactInput, BootstrapContacts
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.readiness import EmailReadiness
from koinon.communications.repositories import OutboxRepository
from koinon.communications.submission import EmailSubmission
from koinon.security.settings import OidcSettings

TID = "00000000-0000-4000-8000-000000000011"
OID = "00000000-0000-4000-8000-000000000012"
ISSUER = f"https://login.microsoftonline.com/{TID}/v2.0"


def observation(**overrides):
    value = dict(
        tenant_id="north",
        issuer=ISSUER,
        client_id="client",
        entra_tenant_id=TID,
        object_id=OID,
        email="admin@example.test",
        display_name="Initial administrator",
        observed_at=datetime.now(UTC),
        source="microsoft_graph_v1",
        account_enabled=True,
        user_type="Member",
    )
    value.update(overrides)
    return BootstrapContactInput.model_validate(value)


async def pending(context, *, expires_in=timedelta(hours=4), created_at=None):
    context.get_bean(OidcSettings).issuer = ISSUER
    row = BootstrapIdentityGrant(
        id=str(uuid4()),
        tenant_id="north",
        canonical_issuer=ISSUER,
        native_client_id="client",
        entra_tenant_id=TID,
        object_id=OID,
        role="admin",
        created_at=created_at or datetime.now(UTC),
        expires_at=(created_at or datetime.now(UTC)) + expires_in,
    )
    await context.get_bean(BootstrapGrantRepository).save(row)
    return row


@pytest.mark.parametrize(
    "locale, phrase", [("en-US", "Sign in with SSO"), ("es-ES", "Inicia sesión con SSO")]
)
async def test_operator_admission_sends_native_welcome_before_login_without_directory(
    email_context, locale, phrase
):
    from koinon.communications.settings import CommunicationsSettings

    context, directory = email_context
    context.get_bean(CommunicationsSettings).default_locale = locale
    await pending(context)
    service = context.get_bean(BootstrapContacts)
    first = await service.admit(observation())
    again = await service.admit(observation())
    assert again.id == first.id
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert len(messages) == 1
    assert messages[0].to == ["admin@example.test"]
    assert "https://brain.test/auth/setup" in messages[0].body_text
    assert phrase in messages[0].body_text and phrase in messages[0].body_html
    assert directory.reads == 0
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "sent"
    assert await state.claim("owned-next") is None


async def test_unknown_bootstrap_welcome_is_never_automatically_submitted_twice(email_context):
    context, _ = email_context
    await pending(context)
    await context.get_bean(BootstrapContacts).admit(observation())
    messages = owned_transport(context, EmailStatus.UNKNOWN)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert len(messages) == 1
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "unknown"
    await context.get_bean(BootstrapContacts).admit(observation())
    assert await state.claim("owned-next") is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"object_id": str(uuid4())},
        {"client_id": "other"},
        {"issuer": "https://wrong.invalid"},
        {"observed_at": datetime.now(UTC) - timedelta(hours=1)},
    ],
)
async def test_unknown_or_stale_operator_contact_cannot_admit(email_context, overrides):
    context, _ = email_context
    await pending(context)
    with pytest.raises(ValueError):
        await context.get_bean(BootstrapContacts).admit(observation(**overrides))
    assert not await context.get_bean(OutboxRepository).find_all(kind="welcome")


@pytest.mark.parametrize("provider_state", ["disabled", "not_configured"])
async def test_disabled_or_absent_provider_records_suppression_without_reenable_backfill(
    email_context, provider_state
):
    context, _ = email_context
    await pending(context)
    readiness = context.get_bean(EmailReadiness)
    readiness.state = provider_state
    first = await context.get_bean(BootstrapContacts).admit(observation())
    event = await context.get_bean(OutboxRepository).find_by_id(first.event_id)
    assert event.status == "suppressed" and event.failure_code == "EMAIL_DISABLED"
    readiness.state = "ready"
    assert (await context.get_bean(BootstrapContacts).admit(observation())).id == first.id
    assert await context.get_bean(CommunicationOutbox).claim("owned-worker") is None


async def test_contact_expiry_after_render_fences_actual_submission(email_context, monkeypatch):
    import asyncio

    context, _ = email_context
    grant = await pending(context, expires_in=timedelta(seconds=2))
    await context.get_bean(BootstrapContacts).admit(observation())
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    original = state.write_payload
    waits = []

    async def expire(*args):
        result = await original(*args)
        await asyncio.sleep(3.1)
        waits.append(datetime.now(UTC))
        assert waits[-1] > grant.expires_at
        return result

    monkeypatch.setattr(state, "write_payload", expire)
    await context.get_bean(EmailSubmission).execute(ticket)
    assert waits
    assert not messages
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "cancelled"


async def test_database_rejects_binding_before_signed_grant_activation(email_context):
    from sqlalchemy import update
    from sqlalchemy.exc import IntegrityError

    from koinon.communications.entities import BootstrapContactRecord
    from koinon.communications.repositories import BootstrapContactRepository

    context, _ = email_context
    await pending(context)
    row = await context.get_bean(BootstrapContacts).admit(observation())

    @transactional
    async def forge():
        await (
            context.get_bean(BootstrapContactRepository)
            ._require_session()
            .execute(
                update(BootstrapContactRecord)
                .where(BootstrapContactRecord.id == row.id)
                .values(canonical_subject=ISSUER + "|invented")
            )
        )

    with pytest.raises(IntegrityError, match="immutable"):
        await forge()


async def activate(context, *, object_id=OID):
    from types import SimpleNamespace

    from pyfly.security.context import SecurityContext
    from starlette.requests import Request

    from koinon.bootstrap.service import BootstrapGrants
    from koinon.communications.ports import WelcomeAdmissionPort
    from koinon.communications.welcome import WelcomeAdmissions

    context.container.register_instance(WelcomeAdmissionPort, context.get_bean(WelcomeAdmissions))
    context.register_bean(BootstrapGrants)
    oidc = context.get_bean(OidcSettings)
    request = Request(dict(type="http", method="GET", path="/login/oauth2/code/koinon", headers=[]))
    registration = SimpleNamespace(client_id="client", issuer_uri=ISSUER, redirect_uri=oidc.redirect_uri)
    login = SecurityContext(
        user_id="real-pairwise",
        attributes=dict(iss=ISSUER, sub="real-pairwise", oid=object_id, tid=TID, aud="client", azp="client"),
    )
    await context.get_bean(BootstrapGrants).observe_login(request, registration, login)
    await context.get_bean(BootstrapGrants).observe_login(request, registration, login)


async def test_signed_activation_reuses_initial_event_and_never_submits_second_welcome(email_context):
    from koinon.catalog.repositories import MembershipRepository

    context, directory = email_context
    await pending(context)
    admitted = await context.get_bean(BootstrapContacts).admit(observation())
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    await activate(context)
    events = await context.get_bean(OutboxRepository).find_all(kind="welcome")
    assert len(events) == 1 and events[0].id == admitted.event_id
    assert events[0].owner_subject == ISSUER + "|real-pairwise"
    assert len(await context.get_bean(MembershipRepository).find_all(subject=events[0].owner_subject)) == 1
    assert len(messages) == 1 and directory.reads == 0
    assert await state.claim("owned-next") is None


async def test_wrong_signed_identity_does_not_bind_operator_contact(email_context):
    from koinon.communications.repositories import BootstrapContactRepository

    context, _ = email_context
    await pending(context)
    row = await context.get_bean(BootstrapContacts).admit(observation())
    await activate(context, object_id=str(uuid4()))
    assert (await context.get_bean(BootstrapContactRepository).find_by_id(row.id)).canonical_subject is None
    assert (await context.get_bean(OutboxRepository).find_by_id(row.event_id)).owner_subject is None


async def test_revoked_administrator_membership_cancels_unsent_bootstrap_welcome(email_context):
    from koinon.catalog.repositories import MembershipRepository

    context, _ = email_context
    await pending(context)
    await context.get_bean(BootstrapContacts).admit(observation())
    await activate(context)
    members = context.get_bean(MembershipRepository)
    row = (await members.find_all(subject=ISSUER + "|real-pairwise"))[0]
    row.active = False
    await members.save(row)
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    ticket = await state.claim("owned-worker")
    await context.get_bean(EmailSubmission).execute(ticket)
    assert not messages
    assert (await context.get_bean(OutboxRepository).find_by_id(ticket.id)).status == "cancelled"


async def test_initial_contact_is_not_a_general_security_or_digest_target(email_context):
    from types import SimpleNamespace

    context, _ = email_context
    await pending(context)
    row = await context.get_bean(BootstrapContacts).admit(observation())
    await activate(context)
    for kind in ("security", "digest", "invitation"):
        event = SimpleNamespace(
            id=row.event_id,
            kind=kind,
            tenant_id="north",
            owner_subject=ISSUER + "|real-pairwise",
            event_json={"bootstrap_contact_id": row.id},
        )
        assert await context.get_bean(BootstrapContacts).prepare(event) is None


async def test_concurrent_operator_imports_have_one_durable_native_pg_admission(email_context):
    import asyncio

    from pyfly.data.relational.datasource_registry import DataSourceRegistry

    context, _ = email_context
    if context.get_bean(DataSourceRegistry).primary.engine.dialect.name != "postgresql":
        pytest.skip("The concurrent row-lock proof requires the owned native PostgreSQL fixture")
    await pending(context)
    service = context.get_bean(BootstrapContacts)
    first, second = await asyncio.gather(service.admit(observation()), service.admit(observation()))
    assert first.id == second.id and first.event_id == second.event_id
    assert len(await context.get_bean(OutboxRepository).find_all(kind="welcome")) == 1


@pytest.mark.parametrize(
    "clock, observed, admitted",
    [
        ("2026-11-01T09:05:00+00:00", "2026-11-01T08:00:00+00:00", False),
        ("2026-11-01T09:05:00+00:00", "2026-11-01T08:55:00+00:00", True),
        ("2026-03-08T10:05:00+00:00", "2026-03-08T09:55:00+00:00", True),
    ],
)
async def test_contact_freshness_and_twenty_four_hour_expiry_use_elapsed_utc_across_dst(
    email_context, monkeypatch, clock, observed, admitted
):
    from zoneinfo import ZoneInfo

    context, _ = email_context
    zone = ZoneInfo("America/Los_Angeles")
    now = datetime.fromisoformat(clock)
    observed_at = datetime.fromisoformat(observed)
    await pending(context, expires_in=timedelta(days=3), created_at=now)

    async def database_clock():
        return now.astimezone(zone)

    monkeypatch.setattr(context.get_bean(OutboxRepository), "clock", database_clock)
    service = context.get_bean(BootstrapContacts)
    body = observation(observed_at=observed_at.astimezone(zone))
    if not admitted:
        with pytest.raises(ValueError, match="fresh"):
            await service.admit(body)
        assert not await context.get_bean(OutboxRepository).find_all(kind="welcome")
    else:
        row = await service.admit(body)
        assert row.observed_at == observed_at
        assert row.expires_at == observed_at + timedelta(hours=24)
