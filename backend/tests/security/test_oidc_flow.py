# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
from types import SimpleNamespace
from urllib.parse import parse_qs, urlencode, urlsplit

from pyfly.security.oauth2.client import ClientRegistration, InMemoryClientRegistrationRepository
from pyfly.session.session import HttpSession
from starlette.requests import Request

from koinon.security.oidc import VerifiedOidcLoginHandler

ISSUER = "https://identity.example.test/realms/koinon"


def request(session, query=""):
    value = Request(
        {
            "type": "http",
            "path": "/login/oauth2/code/koinon",
            "method": "GET",
            "headers": [],
            "query_string": query.encode(),
            "path_params": {"registration_id": "koinon"},
        }
    )
    value.state.session = session
    return value


def handler(**kwargs):
    registration = ClientRegistration(
        registration_id="koinon",
        client_id="browser",
        issuer_uri=ISSUER,
        jwks_uri=f"{ISSUER}/certs",
        authorization_uri=f"{ISSUER}/auth",
        token_uri=f"{ISSUER}/token",
        redirect_uri="https://app.example.test/login/oauth2/code/koinon",
        scopes=["openid"],
        require_iss=True,
    )
    return VerifiedOidcLoginHandler(InMemoryClientRegistrationRepository(registration), **kwargs)


async def test_native_authorization_pkce_state_nonce_session_rotation_and_replay():
    login = handler()
    session = HttpSession("before-auth", is_new=True)
    redirect = await login._handle_authorization(request(session))
    query = parse_qs(urlsplit(redirect.headers["location"]).query)
    verifier = session.get_attribute("oauth2_pkce_verifier")
    digest = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert query["code_challenge"] == [digest]
    assert query["code_challenge_method"] == ["S256"]
    nonce = session.get_attribute("oauth2_nonce")
    exchanges = []

    async def exchange(registration, code, code_verifier=None):
        exchanges.append((code, code_verifier))
        return {"access_token": "offline-access", "id_token": "offline-id"}

    login._exchange_code = exchange
    login.validator_factory = lambda reg: SimpleNamespace(
        validate=lambda value: {
            "iss": ISSUER,
            "sub": "user-1",
            "aud": "browser",
            "nonce": nonce,
        }
    )
    callback = urlencode({"state": query["state"][0], "code": "one-time-code", "iss": ISSUER})
    bad = await login._handle_callback(request(session, urlencode({"state": "wrong", "code": "code"})))
    assert bad.status_code == 400
    assert exchanges == []
    result = await login._handle_callback(request(session, callback))
    assert result.status_code == 302
    assert exchanges == [("one-time-code", verifier)]
    assert session.id != "before-auth"
    assert session.get_attribute("SECURITY_CONTEXT").attributes == {"iss": ISSUER, "sub": "user-1"}
    assert session.get_attribute("oauth2_state") is None
    assert (await login._handle_callback(request(session, callback))).status_code == 400
    assert len(exchanges) == 1


async def test_native_issuer_response_mismatch_rejected_before_exchange():
    login = handler()
    session = HttpSession("before-auth", is_new=True)
    await login._handle_authorization(request(session))
    query = urlencode(
        {"state": session.get_attribute("oauth2_state"), "code": "code", "iss": "https://wrong.test"}
    )
    assert (await login._handle_callback(request(session, query))).status_code == 400


async def test_strict_native_callback_requires_id_token_without_userinfo():
    login = handler()
    session = HttpSession("before-auth", is_new=True)
    await login.routes()[0].endpoint(request(session))
    called = []

    async def exchange(registration, code, code_verifier=None):
        return {"access_token": "offline-access"}

    async def userinfo(*args):
        called.append(True)
        raise AssertionError("OAuth-only userinfo must not become an OIDC identity")

    login._exchange_code, login._fetch_user_info = exchange, userinfo
    callback = urlencode({"state": session.get_attribute("oauth2_state"), "code": "code", "iss": ISSUER})
    result = await login.routes()[1].endpoint(request(session, callback))
    assert result.status_code == 401
    assert called == []
    assert session.id == "before-auth"
    assert session.get_attribute("SECURITY_CONTEXT") is None


async def test_product_uses_native_public_hooks_and_preserves_verified_raw_claims():
    from pyfly.security.oauth2 import (
        OAuth2AuthenticationSuccessHandler,
        OAuth2AuthorizationRequestCustomizer,
        OidcTokenValidatorFactory,
    )
    from test_identity import token, validator

    observed = []

    class Customize(OAuth2AuthorizationRequestCustomizer):
        async def customize(self, request, registration):
            return {"kc_idp_hint": "north-entra", "prompt": "login", "max_age": "0"}

    class Success(OAuth2AuthenticationSuccessHandler):
        async def on_success(self, request, registration, context):
            assert request.state.session.get_attribute("SECURITY_CONTEXT") is None
            assert request.state.session.id == "before-auth"
            observed.append(context)

    class Factory(OidcTokenValidatorFactory):
        def create(self, registration):
            return validator("browser")

    login = handler(
        authorization_request_customizer=Customize(),
        authentication_success_handler=Success(),
        id_token_validator_factory=Factory(),
        success_uri="http://127.0.0.1:18782",
    )
    session = HttpSession("before-auth", is_new=True)
    redirect = await login.routes()[0].endpoint(request(session))
    query = parse_qs(urlsplit(redirect.headers["location"]).query)
    assert query["kc_idp_hint"] == ["north-entra"]
    assert query["prompt"] == ["login"]
    assert query["max_age"] == ["0"]
    nonce = session.get_attribute("oauth2_nonce")

    async def exchange(registration, code, code_verifier=None):
        return {
            "access_token": "offline-access",
            "id_token": token(
                aud="browser",
                nonce=nonce,
                auth_time=1700000000,
                groups=["research", "reviewers"],
                amr=["pwd", "mfa"],
            ),
        }

    login._exchange_code = exchange
    callback = urlencode({"state": query["state"][0], "code": "one-time-code", "iss": ISSUER})
    result = await login.routes()[1].endpoint(request(session, callback))
    assert result.headers["location"] == "http://127.0.0.1:18782"
    assert observed[0].attributes["auth_time"] == 1700000000
    assert observed[0].attributes["groups"] == ["research", "reviewers"]
    assert observed[0].attributes["amr"] == ["pwd", "mfa"]
    assert observed[0].roles == []
    assert session.id != "before-auth"
