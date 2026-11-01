# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ServiceUnavailableException

from koinon.communications.directory import normalize_recipient
from koinon.corporate_identity.dtos import EntraSettings, GoogleWorkspaceSettings, KeycloakSettings

ENTRA = EntraSettings(kind="entra", tenant_id="11111111-1111-1111-1111-111111111111", client_id="client")
KEYCLOAK = KeycloakSettings(kind="keycloak", issuer="https://identity.test/realms/people", client_id="client")
GOOGLE = GoogleWorkspaceSettings(
    kind="google_workspace", client_id="client", hosted_domains=["example.test"], customer_id="customer"
)
USER = "22222222-2222-2222-2222-222222222222"


def test_keycloak_requires_enabled_and_verified_directory_email():
    raw = dict(id=USER, enabled=True, emailVerified=True, email="person@example.test", firstName="Person")
    person = normalize_recipient(KEYCLOAK, USER, raw)
    assert person.external_subject == USER and person.delivery_address_status == "verified_directory"
    assert person.email == "person@example.test"
    assert (
        normalize_recipient(KEYCLOAK, USER, {**raw, "emailVerified": False}).delivery_address_status
        == "unverified"
    )
    assert (
        normalize_recipient(KEYCLOAK, USER, {**raw, "enabled": False}).delivery_address_status
        == "unavailable"
    )
    assert normalize_recipient(KEYCLOAK, USER, {**raw, "email": None}).delivery_address_status == "missing"


def test_entra_requires_enabled_member_and_explicit_guest_policy():
    raw = dict(
        id=USER, accountEnabled=True, userType="Member", mail="person@example.test", displayName="Person"
    )
    assert normalize_recipient(ENTRA, USER, raw).delivery_address_status == "verified_directory"
    guest = {**raw, "userType": "Guest"}
    assert normalize_recipient(ENTRA, USER, guest).delivery_address_status == "unavailable"
    assert (
        normalize_recipient(ENTRA, USER, guest, allow_entra_guests=True).delivery_address_status
        == "verified_directory"
    )
    assert (
        normalize_recipient(ENTRA, USER, {**raw, "accountEnabled": False}).delivery_address_status
        == "unavailable"
    )
    assert (
        normalize_recipient(ENTRA, USER, {**raw, "accountEnabled": "true"}).delivery_address_status
        == "unavailable"
    )
    assert (
        normalize_recipient(
            ENTRA, USER, {**raw, "mail": None, "userPrincipalName": "person@example.test"}
        ).email
        == "person@example.test"
    )
    assert (
        normalize_recipient(
            ENTRA,
            USER,
            {**guest, "mail": None, "userPrincipalName": "person_example.test#EXT#@tenant.test"},
            allow_entra_guests=True,
        ).delivery_address_status
        == "missing"
    )


def test_google_primary_address_is_authoritative_only_in_configured_customer_domain():
    raw = dict(
        id=USER,
        customerId="customer",
        suspended=False,
        archived=False,
        primaryEmail="person@example.test",
        name={"fullName": "Person"},
    )
    assert normalize_recipient(GOOGLE, USER, raw).delivery_address_status == "verified_directory"
    for change in (
        {"customerId": "other"},
        {"primaryEmail": "person@other.test"},
        {"suspended": True},
        {"archived": True},
    ):
        assert normalize_recipient(GOOGLE, USER, {**raw, **change}).delivery_address_status == "unavailable"


@pytest.mark.parametrize(
    "address",
    [
        "person@example.test\r\nBcc:other@other.test",
        "Two <person@example.test>",
        "person@example.test,other@example.test",
        "person@example.test/escape",
    ],
)
def test_directory_address_cannot_inject_headers_or_multiple_recipients(address):
    raw = dict(id=USER, enabled=True, emailVerified=True, email=address)
    assert normalize_recipient(KEYCLOAK, USER, raw).delivery_address_status == "unavailable"


def test_directory_account_id_must_match_requested_immutable_identity():
    with pytest.raises(ServiceUnavailableException):
        normalize_recipient(
            KEYCLOAK,
            USER,
            dict(id="different", enabled=True, emailVerified=True, email="person@example.test"),
        )
