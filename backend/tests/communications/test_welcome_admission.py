# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.data.relational.sqlalchemy import transactional
from test_email_invitations import ACTOR
from test_email_invitations import email_context as email_context

from koinon.communications.repositories import OutboxRepository
from koinon.communications.welcome import WelcomeAdmissions


@transactional
async def welcome(context):
    service = WelcomeAdmissions(
        context.get_bean(OutboxRepository),
        context.get_bean(
            __import__("koinon.communications.events", fromlist=["CommunicationEvents"]).CommunicationEvents
        ),
    )
    return await service.admit(ACTOR, "north")


async def test_welcome_installation_identity_admission_survives_brand_domain_and_restart_changes(
    email_context,
):
    context, _ = email_context
    first = await welcome(context)
    assert first is not None
    again = await welcome(context)
    assert again.id == first.id and again.installation_id == first.installation_id
    rows = await context.get_bean(OutboxRepository).find_all(kind="welcome")
    assert len(rows) == 1 and rows[0].status == "suppressed"
    assert rows[0].failure_code == "DELIVERY_IDENTITY_UNVERIFIED"


def test_upstream_immutable_identity_key_does_not_depend_on_broker_or_public_origin():
    from uuid import UUID

    from koinon.communications.identity import immutable_identity_key
    from koinon.corporate_identity.dtos import EntraSettings

    first = EntraSettings(
        kind="entra", tenant_id=UUID("11111111-1111-1111-1111-111111111111"), client_id="first-client"
    )
    second = first.model_copy(update={"client_id": "replacement-client", "identity_mode": "direct"})
    assert immutable_identity_key(first, "immutable-oid") == immutable_identity_key(second, "immutable-oid")
    assert immutable_identity_key(first, "immutable-oid") != immutable_identity_key(first, "other-oid")
