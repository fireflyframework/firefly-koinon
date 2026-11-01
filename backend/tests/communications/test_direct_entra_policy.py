# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import replace
from types import SimpleNamespace

import pytest
from pyfly.kernel import InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.corporate_identity.broker import CorporateBrokerPolicy
from koinon.corporate_identity.dtos import EntraSettings, IdentityProviderInput
from koinon.corporate_identity.policy import IdentityPolicy, verified_identity
from koinon.corporate_identity.service import CorporateIdentityService
from koinon.corporate_identity.settings import IdentitySettings

TENANT = "11111111-1111-1111-1111-111111111111"
OBJECT = "22222222-2222-2222-2222-222222222222"
CLIENT = "33333333-3333-3333-3333-333333333333"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"


def policy():
    return IdentityPolicy(
        "provider",
        "entra",
        ISSUER,
        None,
        TENANT,
        identity_mode="direct",
        native_client_id=CLIENT,
        native_api_audience="api://" + CLIENT,
    )


def claims(**overrides):
    return {
        "iss": ISSUER,
        "sub": "pairwise-canonical-sub",
        "oid": OBJECT,
        "tid": TENANT,
        "aud": CLIENT,
        **overrides,
    }


def test_direct_entra_uses_verified_pairwise_sub_and_immutable_oid_with_server_pins():
    identity = verified_identity(policy(), claims())
    assert identity.subject == ISSUER + "|pairwise-canonical-sub"
    assert identity.external_subject == OBJECT
    assert verified_identity(policy(), claims(aud=[CLIENT])).external_subject == OBJECT
    assert (
        verified_identity(policy(), claims(aud=[CLIENT, "api://" + CLIENT], azp=CLIENT)).external_subject
        == OBJECT
    )
    assert verified_identity(policy(), claims(aud="api://" + CLIENT, appid=CLIENT)).external_subject == OBJECT


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://other.test"},
        {"tid": "44444444-4444-4444-4444-444444444444"},
        {"oid": "email@example.test"},
        {"aud": "other-client"},
        {"aud": [CLIENT, "api://" + CLIENT]},
        {"aud": "api://" + CLIENT},
        {"aud": CLIENT, "azp": "other-client"},
        {"aud": [CLIENT, "api://" + CLIENT], "azp": CLIENT, "appid": "other-client"},
        {"koinon_identity_provider": "broker"},
        {"koinon_external_oid": OBJECT},
        {"tid": ""},
    ],
)
def test_direct_entra_rejects_wrong_audience_tenant_client_and_broker_impersonation(changes):
    with pytest.raises(AccessDenied):
        verified_identity(policy(), claims(**changes))


def test_direct_is_explicit_and_unpinned_policy_or_legacy_broker_does_not_admit_raw_claims():
    with pytest.raises(AccessDenied):
        verified_identity(replace(policy(), native_client_id=None), claims())
    legacy = IdentityPolicy("provider", "entra", ISSUER, "broker", TENANT)
    with pytest.raises(AccessDenied):
        verified_identity(legacy, claims())
    configured = IdentityProviderInput(
        kind="entra",
        name="Corporate users",
        settings={"kind": "entra", "tenant_id": TENANT, "client_id": CLIENT, "identity_mode": "direct"},
    )
    assert configured.broker_alias is None


async def test_direct_provider_local_policy_checks_the_native_binding_without_a_keycloak_broker_call():
    native = SimpleNamespace(issuer=ISSUER, client_id=CLIENT)
    row = SimpleNamespace(
        kind="entra",
        broker_alias=None,
        canonical_issuer=ISSUER,
        settings_json={"identity_mode": "direct", "tenant_id": TENANT, "client_id": CLIENT},
    )
    checks = CorporateBrokerPolicy(IdentitySettings(), native, None)
    assert (await checks.check(row))["verified"] is True
    row.settings_json["client_id"] = "other-client"
    assert (await checks.check(row))["verified"] is False


def test_direct_provider_mode_does_not_allow_changing_the_stored_provider_kind():
    service = CorporateIdentityService.__new__(CorporateIdentityService)
    service.oidc = SimpleNamespace(issuer=ISSUER, client_id=CLIENT)
    settings = EntraSettings(kind="entra", tenant_id=TENANT, client_id=CLIENT, identity_mode="direct")
    with pytest.raises(InvalidRequestException):
        service._configuration("keycloak", None, settings)
