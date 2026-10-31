# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.security.oidc import ApiBearerFilter, IdentityTokenValidator, VerifiedOidcLoginHandler
from koinon.tokens.service import PREFIX

ISSUER = "https://identity.example.test/realms/koinon"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def validator(audience="koinon-api", **options):
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    public.update(kid="presentation", use="sig", alg="RS256")
    return IdentityTokenValidator(
        ISSUER + "/certs",
        issuer=ISSUER,
        audiences=[audience],
        leeway=0,
        jwks_fetcher=lambda *_args, **_kwargs: json.dumps({"keys": [public]}).encode(),
        **options,
    )


def token(**overrides):
    claims = {
        "iss": ISSUER,
        "sub": "person",
        "aud": "koinon-api",
        "iat": int(time.time()) - 1,
        "exp": int(time.time()) + 300,
    }
    claims.update(overrides)
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "presentation"})


def request(authorization=None):
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    return Request({"type": "http", "path": "/api/v1/catalog", "method": "GET", "headers": headers})


def test_native_validation_keeps_selected_claims_and_explicit_clear_without_granting_roles():
    context = validator().to_security_context(
        token(
            job_title="Engineer",
            manager_external_subject=None,
            roles=["admin"],
            password="private",
        )
    )
    assert context.attributes.get("job_title") == "Engineer"
    assert "manager_external_subject" in context.attributes
    assert context.attributes["manager_external_subject"] is None
    assert type(context.attributes["iat"]) is int
    assert "password" not in context.attributes and context.roles == []


class Observer:
    def __init__(self):
        self.contexts = []

    async def observe_bearer(self, context):
        assert SecurityContextHolder.get_context() is context
        self.contexts.append(context)


async def next_handler(req):
    return JSONResponse({"authenticated": req.state.security_context.is_authenticated})


async def test_only_native_verified_bearer_reaches_the_corporate_observer():
    observer = Observer()
    middleware = ApiBearerFilter(validator(), observer=observer)
    response = await middleware.do_filter(request("Bearer " + token()), next_handler)
    assert response.status_code == 200 and len(observer.contexts) == 1
    assert observer.contexts[0].attributes["iss"] == ISSUER
    for credential in ["bad", token(aud="different"), token(iss="https://other.test")]:
        assert (await middleware.do_filter(request("Bearer " + credential), next_handler)).status_code == 401
    await middleware.do_filter(request(), next_handler)
    assert len(observer.contexts) == 1


async def test_personal_token_never_establishes_a_corporate_binding():
    class Tokens:
        async def authenticate(self, _secret):
            return SecurityContext(
                user_id="person",
                attributes={
                    "iss": ISSUER,
                    "sub": "person",
                    "koinon_token": {"scopes": ["catalog:read"]},
                },
            )

    observer = Observer()
    response = await ApiBearerFilter(validator(), tokens=Tokens(), observer=observer).do_filter(
        request("Bearer " + PREFIX + "fictional"),
        next_handler,
    )
    assert response.status_code == 200 and observer.contexts == []


def test_extra_claims_are_operator_selected_and_identical_in_browser_and_api():
    from koinon.security.presentation_claims import PresentationClaimSettings

    settings = PresentationClaimSettings(extra_names=["division_title"])
    api = validator(presentation_claims=settings)
    encoded = token(division_title="Operations", unrelated_private_data="not selected")
    assert api.to_security_context(encoded).attributes["division_title"] == "Operations"
    assert "unrelated_private_data" not in api.to_security_context(encoded).attributes
    handler = VerifiedOidcLoginHandler(
        SimpleNamespace(),
        presentation_claims=settings,
        validator_factory=lambda _registration: validator("browser", presentation_claims=settings),
    )
    context = handler._validate_id_token(
        SimpleNamespace(client_id="browser", issuer_uri=ISSUER),
        token(aud="browser", nonce="review", division_title=None),
        "review",
    )
    assert context is not None and context.attributes["division_title"] is None


@pytest.mark.parametrize("name", ["roles", "email", "clientSecret", "koinon_token", "manager.id", "*"])
def test_operator_claim_selection_cannot_copy_identity_authority_or_credentials(name):
    from koinon.security.presentation_claims import PresentationClaimSettings

    with pytest.raises(ValueError):
        PresentationClaimSettings(extra_names=[name])


@pytest.mark.parametrize("value", ["x" * 513, ["Director"], {"secret": "private"}, True, "bad\nvalue"])
def test_invalid_claim_values_are_bounded_and_not_converted_to_a_clear(value):
    context = validator().to_security_context(token(job_title=value))
    assert context.attributes["job_title"] == {"invalid": True}


async def test_optional_profile_observation_failure_does_not_expose_errors_or_change_authority(caplog):
    class Unavailable:
        async def observe_bearer(self, _context):
            raise RuntimeError("private-provider-credential")

    response = await ApiBearerFilter(validator(), observer=Unavailable()).do_filter(
        request("Bearer " + token()),
        next_handler,
    )
    assert response.status_code == 200
    assert "private-provider-credential" not in caplog.text
