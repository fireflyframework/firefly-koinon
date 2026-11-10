# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real signed-token validation via native JWKS, without a provider request."""

import json
import time

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.oauth import SourceOAuthConfig
from pyfly.client import HttpxClientAdapter

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
TENANT = "12345678-1234-1234-1234-123456789012"


def signed(**changes):
    claims = {
        "iss": "https://accounts.google.com",
        "aud": "content-client",
        "sub": "stable-subject",
        "nonce": "bound-nonce",
        "iat": int(time.time()),
        "exp": int(time.time()) + 120,
        **changes,
    }
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "test-key"})


def native_client(seen):
    def response(request):
        seen.append(request)
        assert request.url.host in {"www.googleapis.com", "login.microsoftonline.com"}
        assert "authorization" not in request.headers and "cookie" not in request.headers
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
        return httpx.Response(200, json={"keys": [{**jwk, "kid": "test-key", "use": "sig", "alg": "RS256"}]})

    return HttpxClientAdapter(transport=httpx.MockTransport(response), trust_env=False)


async def test_verified_provider_subject_not_email_is_the_account_identity():
    from koinon.integrations.content_sources.identity import SourceIdentityVerifier

    config = SourceOAuthConfig("google_drive", "content-client", "https://app.example/callback")
    requests = []
    async with SourceIdentityVerifier(
        config, http_client=native_client(requests), owns_http_client=True
    ) as identity:
        account = await identity.verify(signed(email="same@example.invalid"), nonce="bound-nonce")
    assert account.subject == "stable-subject" and account.provider == "google_drive"
    assert account.tenant_id is None
    assert len(requests) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"iss": "https://attacker.invalid"},
        {"aud": "login-client"},
        {"nonce": "other-nonce"},
        {"exp": 1},
        {"sub": ""},
        {"azp": "other-client"},
    ],
)
async def test_wrong_issuer_audience_nonce_expiry_or_authorized_party_cannot_bind(changes):
    from koinon.integrations.content_sources.identity import SourceIdentityVerifier

    config = SourceOAuthConfig("google_drive", "content-client", "https://app.example/callback")
    async with SourceIdentityVerifier(
        config, http_client=native_client([]), owns_http_client=True
    ) as identity:
        with pytest.raises(SourceError, match="invalid_identity"):
            await identity.verify(signed(**changes), nonce="bound-nonce")


async def test_graph_account_is_bound_to_exact_configured_tenant_and_oid():
    from koinon.integrations.content_sources.identity import SourceIdentityVerifier

    config = SourceOAuthConfig(
        "sharepoint", "content-client", "https://app.example/callback", tenant_id=TENANT
    )
    claims = {
        "iss": f"https://login.microsoftonline.com/{TENANT}/v2.0",
        "tid": TENANT,
        "oid": "22345678-1234-1234-1234-123456789012",
    }
    async with SourceIdentityVerifier(
        config, http_client=native_client([]), owns_http_client=True
    ) as identity:
        account = await identity.verify(signed(**claims), nonce="bound-nonce")
        assert account.subject == claims["oid"] and account.tenant_id == TENANT
        with pytest.raises(SourceError, match="invalid_identity"):
            await identity.verify(signed(**{**claims, "tid": "other"}), nonce="bound-nonce")


async def test_jwks_fetch_does_not_forward_a_borrowed_clients_credentials():
    from koinon.integrations.content_sources.identity import SourceIdentityVerifier

    def respond(request):
        assert "authorization" not in request.headers and "cookie" not in request.headers
        jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(KEY.public_key()))
        return httpx.Response(200, json={"keys": [{**jwk, "kid": "test-key"}]})

    async with httpx.AsyncClient(
        headers={"Authorization": "Bearer synthetic-foreign", "Cookie": "session=synthetic"},
        transport=httpx.MockTransport(respond),
        trust_env=False,
    ) as client:
        config = SourceOAuthConfig("google_drive", "content-client", "https://app.example/callback")
        async with SourceIdentityVerifier(config, http_client=HttpxClientAdapter(client=client)) as identity:
            assert (await identity.verify(signed(), nonce="bound-nonce")).subject == "stable-subject"
        assert not client.is_closed
