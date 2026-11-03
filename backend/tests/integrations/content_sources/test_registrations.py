# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.registrations import SourceRegistrations
from koinon.integrations.content_sources.settings import ContentSourceSettings


@pytest.mark.parametrize("host", ["localhost", "127.0.0.1", "[::1]"])
def test_local_registration_requires_literal_boolean_opt_in_and_binds_it_to_challenge(host):
    settings = ContentSourceSettings(
        providers={
            "google_drive": {
                "client_id": "source-client",
                "client_secret": "synthetic",
                "redirect_uri": f"http://{host}:19000/sources/callback",
            }
        }
    )
    registrations = SourceRegistrations(settings)
    with pytest.raises(SourceError):
        registrations.get("google_drive")
    settings.providers["google_drive"]["allow_loopback_http"] = True
    snapshot = registrations.get("google_drive")
    assert snapshot.config.allow_loopback_http is True
    settings.providers["google_drive"]["allow_loopback_http"] = False
    with pytest.raises(SourceError):
        registrations.require_current(snapshot)


@pytest.mark.parametrize("value", ["true", "false", 1, 0])
def test_loopback_option_rejects_truthy_strings_and_numbers(value):
    registrations = SourceRegistrations(
        ContentSourceSettings(
            providers={
                "google_drive": {
                    "client_id": "source-client",
                    "client_secret": "synthetic",
                    "redirect_uri": "https://app.example.test/sources/callback",
                    "allow_loopback_http": value,
                }
            }
        )
    )
    with pytest.raises(SourceError):
        registrations.get("google_drive")


@pytest.mark.parametrize(
    "uri",
    [
        "http://app.example.test/callback",
        "http://localhost.evil.test/callback",
        "http://192.168.1.5/callback",
    ],
)
def test_loopback_opt_in_never_allows_plain_http_to_remote_hosts(uri):
    registrations = SourceRegistrations(
        ContentSourceSettings(
            providers={
                "google_drive": {
                    "client_id": "source-client",
                    "client_secret": "synthetic",
                    "redirect_uri": uri,
                    "allow_loopback_http": True,
                }
            }
        )
    )
    with pytest.raises(SourceError):
        registrations.get("google_drive")


async def test_owned_native_oauth_exchange_preserves_validated_loopback_callback(monkeypatch):
    from urllib.parse import parse_qs

    import httpx
    from koinon.integrations.content_sources import oauth as source_oauth
    from pyfly.oauth2 import OAuth2Client, generate_pkce

    config = source_oauth.SourceOAuthConfig(
        "google_drive", "client", "http://127.0.0.1:19000/callback", allow_loopback_http=True
    )

    def response(request):
        assert parse_qs(request.content.decode())["redirect_uri"] == [config.redirect_uri]
        return httpx.Response(
            200, json={"access_token": "synthetic", "token_type": "Bearer", "scope": " ".join(config.scopes)}
        )

    def client(*args, **kwargs):
        return OAuth2Client(
            *args,
            **kwargs,
            transport=httpx.MockTransport(response),
        )

    monkeypatch.setattr(source_oauth, "OAuth2Client", client)
    async with source_oauth.ReadOnlySourceOAuth(config) as oauth:
        result = await oauth.exchange_code("synthetic-code", code_verifier=generate_pkce().verifier)
        assert result.access_token == "synthetic"
