# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opaque references never turn browser-controlled labels into identity authority."""

import base64
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException

from koinon.communications.crypto import CommunicationsCipher, RecipientReferences
from koinon.communications.dtos import EmailInvitationInput
from koinon.corporate_identity.settings import IdentitySettings


@pytest.fixture
def references():
    settings = IdentitySettings(master_key=base64.urlsafe_b64encode(b"k" * 32).decode())
    return RecipientReferences(CommunicationsCipher(settings))


def issue(references, **overrides):
    values = dict(
        actor="https://issuer.test|admin",
        tenant_id="north",
        provider_id="provider",
        provider_revision=3,
        external_subject="immutable-user-id",
        now=datetime(2026, 10, 31, tzinfo=UTC),
    )
    values.update(overrides)
    return references.issue(**values)


def test_reference_is_opaque_context_bound_and_expires(references):
    token = issue(references)
    assert "immutable-user-id" not in token and "issuer.test" not in token
    expected = dict(
        actor="https://issuer.test|admin", tenant_id="north", now=datetime(2026, 10, 31, tzinfo=UTC)
    )
    value = references.open(token, **expected)
    assert value.provider_id == "provider" and value.provider_revision == 3
    assert value.external_subject == "immutable-user-id"
    for change in (
        {"actor": "https://issuer.test|other"},
        {"tenant_id": "south"},
        {"now": expected["now"] + timedelta(minutes=6)},
        {"now": expected["now"] - timedelta(minutes=1)},
    ):
        with pytest.raises(InvalidRequestException) as failure:
            references.open(token, **{**expected, **change})
        assert failure.value.code == "RECIPIENT_REFERENCE_UNAVAILABLE"
        assert token not in str(failure.value)


def test_delivery_cipher_purpose_and_tenant_are_separate_from_recipient_reference(references):
    token = issue(references)
    with pytest.raises(ServiceUnavailableException):
        references.cipher.open("north", "delivery", token)
    ciphertext = references.cipher.seal("north", "delivery", {"to": "person@example.test"})
    assert "person@example.test" not in ciphertext
    assert references.cipher.open("north", "delivery", ciphertext)["to"] == "person@example.test"
    with pytest.raises(ServiceUnavailableException):
        references.cipher.open("south", "delivery", ciphertext)


@pytest.mark.parametrize(
    "extra",
    [
        {"email": "other@example.test"},
        {"token": "credential"},
        {"url": "https://other.test"},
        {"subject": "other-user"},
    ],
)
def test_email_invitation_input_accepts_only_server_reference(extra):
    with pytest.raises(ValueError):
        EmailInvitationInput(recipient_ref="opaque-reference", role="viewer", **extra)


def test_invalid_master_key_fails_closed_without_echo():
    cipher = CommunicationsCipher(IdentitySettings(master_key="not-a-key"))
    with pytest.raises(ServiceUnavailableException) as failure:
        cipher.seal("north", "delivery", {"to": "person@example.test"})
    assert "not-a-key" not in str(failure.value)
