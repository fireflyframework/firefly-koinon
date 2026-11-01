# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Direct directory identity must survive the actual signed native token boundary."""

import json
import time
from dataclasses import replace
from urllib.parse import urlencode

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pyfly.security.oauth2 import OAuth2AuthenticationSuccessHandler, OidcTokenValidatorFactory
from pyfly.security.oauth2.client import ClientRegistration, InMemoryClientRegistrationRepository
from pyfly.session.session import HttpSession
from starlette.requests import Request

from koinon.catalog.errors import AccessDenied
from koinon.corporate_identity.policy import IdentityPolicy, verified_identity
from koinon.security.oidc import IdentityTokenValidator, VerifiedOidcLoginHandler

TENANT = "00000000-0000-4000-8000-000000000001"
OBJECT = "00000000-0000-4000-8000-000000000002"
CLIENT = "inert-browser-client"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
POLICY = IdentityPolicy(
    "inert-provider",
    "entra",
    ISSUER,
    None,
    external_tenant_id=TENANT,
    identity_mode="direct",
    native_client_id=CLIENT,
)


def validator(audience=CLIENT):
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    key.update(kid="inert-key", use="sig", alg="RS256")
    return IdentityTokenValidator(
        ISSUER + "/certs",
        issuer=ISSUER,
        audiences=[audience],
        jwks_fetcher=lambda *args, **kwargs: json.dumps({"keys": [key]}).encode(),
        leeway=0,
    )


def signed(**overrides):
    claims = {
        "iss": ISSUER,
        "sub": "signed-pairwise-subject",
        "tid": TENANT,
        "oid": OBJECT,
        "aud": CLIENT,
        "azp": CLIENT,
        "appid": CLIENT,
        "exp": int(time.time()) + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "inert-key"})


def request(session, query=""):
    value = Request(
        {
            "type": "http",
            "path": "/login/oauth2/code/koinon",
            "method": "GET",
            "headers": [(b"x-oid", b"forged-object"), (b"x-tid", b"forged-tenant")],
            "query_string": query.encode(),
            "path_params": {"registration_id": "koinon"},
        }
    )
    value.state.session = session
    return value


@pytest.mark.parametrize("audience", [CLIENT, [CLIENT, "inert-second-audience"]])
async def test_signed_native_oidc_callback_preserves_direct_identity_without_userinfo_merge(audience):
    observed, userinfo = [], []

    class Factory(OidcTokenValidatorFactory):
        def create(self, registration):
            return validator()

    class Success(OAuth2AuthenticationSuccessHandler):
        async def on_success(self, request, registration, context):
            observed.append(verified_identity(POLICY, context.attributes))

    registration = ClientRegistration(
        registration_id="koinon",
        client_id=CLIENT,
        issuer_uri=ISSUER,
        jwks_uri=ISSUER + "/certs",
        authorization_uri=ISSUER + "/authorize",
        token_uri=ISSUER + "/token",
        user_info_uri="https://userinfo.invalid/claims",
        redirect_uri="https://app.invalid/login/oauth2/code/koinon",
        scopes=["openid"],
        require_iss=True,
    )
    login = VerifiedOidcLoginHandler(
        InMemoryClientRegistrationRepository(registration),
        id_token_validator_factory=Factory(),
        authentication_success_handler=Success(),
    )
    session = HttpSession("before-auth", is_new=True)
    await login.routes()[0].endpoint(request(session))
    nonce = session.get_attribute("oauth2_nonce")

    async def exchange(*args):
        return {"access_token": "inert-access", "id_token": signed(nonce=nonce, aud=audience)}

    async def forged_userinfo(*args):
        userinfo.append(True)
        return {
            "iss": "https://forged.invalid",
            "sub": "forged-sub",
            "aud": "forged-audience",
            "oid": "00000000-0000-4000-8000-000000000099",
            "tid": TENANT,
        }

    login._exchange_code, login._fetch_user_info = exchange, forged_userinfo
    query = urlencode(
        {
            "state": session.get_attribute("oauth2_state"),
            "code": "inert-code",
            "iss": ISSUER,
            "oid": "forged-object",
            "tid": "forged-tenant",
            "aud": "forged-audience",
        }
    )
    response = await login.routes()[1].endpoint(request(session, query))
    assert response.status_code == 302
    assert userinfo == []
    assert observed[0].subject == ISSUER + "|signed-pairwise-subject"
    assert observed[0].external_subject == OBJECT
    context = session.get_attribute("SECURITY_CONTEXT")
    assert context.attributes["aud"] == audience
    assert context.attributes["oid"] == OBJECT
    assert context.attributes["tid"] == TENANT
    assert context.attributes["azp"] == context.attributes["appid"] == CLIENT
    assert session.id != "before-auth"
    assert context.roles == []


def test_signed_api_jwt_keeps_native_audience_and_directory_identity_without_oid_as_sub():
    context = validator("inert-api-audience").to_security_context(signed(aud="inert-api-audience"))
    identity = verified_identity(
        replace(POLICY, native_api_audience="inert-api-audience"), context.attributes
    )
    assert identity.subject == ISSUER + "|signed-pairwise-subject"
    assert identity.external_subject == OBJECT
    assert context.attributes["aud"] == "inert-api-audience"
    assert context.user_id != OBJECT


@pytest.mark.parametrize(
    "overrides",
    [
        {"tid": "00000000-0000-4000-8000-000000000099"},
        {"oid": [OBJECT]},
        {"appid": "another-client"},
        {"azp": "another-client"},
    ],
)
def test_signed_but_wrong_directory_or_client_claims_still_fail_closed(overrides):
    context = validator().to_security_context(signed(**overrides))
    with pytest.raises(AccessDenied):
        verified_identity(POLICY, context.attributes)


@pytest.mark.parametrize("name", ["oid", "tid", "iss", "sub", "aud", "azp", "appid"])
def test_presentation_configuration_cannot_rewrite_verified_identity_claims(name):
    from koinon.security.presentation_claims import PresentationClaimSettings

    with pytest.raises(ValueError):
        PresentationClaimSettings(extra_names=[name])
