# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ConflictException, InvalidRequestException
from test_membership_events import communications as communications

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.communications.administration import CommunicationsAdministration
from koinon.communications.dtos import CommunicationPolicyInput

ACTOR = "https://issuer.test|admin"


async def test_policy_is_revisioned_and_sender_selection_cannot_assert_verification(communications):
    admin = communications.get_bean(CommunicationsAdministration)
    initial = await admin.policy(ACTOR, "north")
    assert initial.revision == 0 and initial.default_digest == "off"
    body = CommunicationPolicyInput(
        expected_revision=0,
        rules=[dict(kind=item.kind, inbox=item.inbox, email=item.email) for item in initial.rules],
        default_locale="es-ES",
    )
    assert (await admin.update_policy(ACTOR, "north", body)).revision == 1
    with pytest.raises(ConflictException):
        await admin.update_policy(ACTOR, "north", body)
    with pytest.raises(InvalidRequestException):
        await admin.update_policy(
            ACTOR,
            "north",
            body.model_copy(update={"expected_revision": 1, "sender_id": "not-operator-verified"}),
        )


async def test_history_is_separately_authorized_paged_and_never_returns_ciphertext_or_credentials(
    communications,
):
    await communications.get_bean(CatalogService).create_member(
        ACTOR, "north", subject="https://issuer.test|person", role="viewer"
    )
    admin = communications.get_bean(CommunicationsAdministration)
    result = await admin.deliveries(ACTOR, "north", page_size=1)
    assert result.total == 1 and len(result.items) == 1
    output = result.model_dump(mode="json")
    assert "payload_ciphertext" not in str(output) and "token" not in str(output)
    with pytest.raises(AccessDenied):
        await admin.deliveries("https://issuer.test|person", "north")
    assert (await admin.deliveries(ACTOR, "south")).total == 0
