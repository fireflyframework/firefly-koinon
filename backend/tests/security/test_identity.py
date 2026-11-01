# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from pyfly.kernel.exceptions import SecurityException, UnauthorizedException
from pyfly.security.context import SecurityContext
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.security.identity import RequestAuthorization, identity_from_request
from koinon.security.oidc import ApiBearerFilter, IdentityTokenValidator, VerifiedOidcLoginHandler

ISSUER = "https://identity.example.test/realms/koinon"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def validator(audience="koinon-api"):
    key = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
    key.update(kid="test-key", use="sig", alg="RS256")

    def fetch(uri, *, timeout, max_bytes):
        return json.dumps({"keys": [key]}).encode()

    return IdentityTokenValidator(
        f"{ISSUER}/certs", issuer=ISSUER, audiences=[audience], jwks_fetcher=fetch, leeway=0
    )


def token(**overrides):
    claims = {"iss": ISSUER, "sub": "user-1", "aud": "koinon-api", "exp": int(time.time()) + 300}
    claims.update(overrides)
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "test-key"})


def request(path="/api/v1/catalog", context=None, authorization=None):
    headers = [] if authorization is None else [(b"authorization", authorization.encode())]
    req = Request({"type": "http", "path": path, "method": "GET", "headers": headers})
    if context is not None:
        req.state.security_context = context
    return req


def test_native_validator_preserves_verified_canonical_subject():
    context = validator().to_security_context(token())
    identity = identity_from_request(request(context=context))
    assert identity.subject == f"{ISSUER}|user-1"
    assert identity.authenticated
    assert identity.authentication_method == "bearer"


@pytest.mark.parametrize(
    "claims",
    [
        {"iss": "https://other.example.test"},
        {"aud": "other-api"},
        {"exp": int(time.time()) - 100},
        {"sub": ""},
    ],
)
def test_native_validator_rejects_wrong_identity_claims(claims):
    with pytest.raises(SecurityException):
        validator().to_security_context(token(**claims))


def test_native_validator_rejects_bad_signature():
    forged = jwt.encode(
        {"iss": ISSUER, "sub": "user-1", "aud": "koinon-api", "exp": int(time.time()) + 300},
        rsa.generate_private_key(public_exponent=65537, key_size=2048),
        algorithm="RS256",
        headers={"kid": "test-key"},
    )
    with pytest.raises(SecurityException):
        validator().to_security_context(forged)


def test_identity_requires_verified_issuer_and_sub_never_email():
    context = SecurityContext(user_id="person@example.test", attributes={"email": "person@example.test"})
    with pytest.raises(UnauthorizedException):
        identity_from_request(request(context=context))


async def test_api_cookie_principal_cannot_replace_missing_bearer():
    req = request(context=validator().to_security_context(token()))

    async def next_handler(req):
        return JSONResponse({"authenticated": req.state.security_context.is_authenticated})

    result = await ApiBearerFilter(validator()).do_filter(req, next_handler)
    assert json.loads(result.body) == {"authenticated": False}


async def test_bad_bearer_cannot_fall_back_to_cookie():
    req = request(context=validator().to_security_context(token()), authorization="Bearer bad")
    result = await ApiBearerFilter(validator()).do_filter(req, lambda req: None)
    assert result.status_code == 401


async def test_browser_session_survives_and_bearer_is_rejected():
    context = validator().to_security_context(token())
    req = request("/bff/api/v1/catalog", context=context)

    async def next_handler(req):
        return JSONResponse({"subject": identity_from_request(req).subject})

    assert (await ApiBearerFilter(validator()).do_filter(req, next_handler)).status_code == 200
    req = request("/bff/api/v1/catalog", context=context, authorization=f"Bearer {token()}")
    assert (await ApiBearerFilter(validator()).do_filter(req, next_handler)).status_code == 400


async def test_membership_checked_each_call_and_revocation_immediate():
    class Catalog:
        allowed = True
        calls = []

        async def authorize(self, subject, tenant_id, permission, workspace_id=None):
            self.calls.append((subject, tenant_id, permission, workspace_id))
            if not self.allowed:
                raise PermissionError("revoked")

    catalog = Catalog()
    authorization = RequestAuthorization(catalog)
    req = request(context=validator().to_security_context(token()))
    identity = await authorization.require_permission(req, "tenant-a", "catalog:read", "workspace-a")
    assert catalog.calls == [(identity.subject, "tenant-a", "catalog:read", "workspace-a")]
    catalog.allowed = False
    with pytest.raises(PermissionError, match="revoked"):
        await authorization.require_permission(req, "tenant-a", "catalog:read", "workspace-a")
    assert len(catalog.calls) == 2


def test_browser_id_token_signature_nonce_audience():
    handler = VerifiedOidcLoginHandler(SimpleNamespace(), validator_factory=lambda reg: validator("browser"))
    registration = SimpleNamespace(client_id="browser", issuer_uri=ISSUER)
    good = token(aud="browser", nonce="expected")
    context = handler._validate_id_token(registration, good, "expected")
    assert context.attributes == {"iss": ISSUER, "sub": "user-1", "aud": "browser"}
    assert handler._validate_id_token(registration, good, "wrong") is None
    assert handler._validate_id_token(registration, good, None) is None
    assert handler._validate_id_token(registration, token(aud="wrong", nonce="expected"), "expected") is None
