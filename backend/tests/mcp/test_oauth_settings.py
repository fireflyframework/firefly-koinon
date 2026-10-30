# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from cryptography.fernet import Fernet

from koinon.mcp_auth.settings import McpOAuthSettings


def valid(**changes):
    return McpOAuthSettings(
        **{
            "enabled": True,
            "encryption_key": Fernet.generate_key().decode(),
            "clients": [
                {
                    "client_id": "client",
                    "name": "Chat client",
                    "redirect_uris": ["https://client.example/callback"],
                    "scopes": ["catalog:read"],
                }
            ],
            **changes,
        }
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"encryption_key": ""},
        {"encryption_key": "invalid"},
        {"code_ttl_seconds": 301},
        {"code_ttl_seconds": True},
        {"access_ttl_seconds": 120.5},
    ],
)
def test_oauth_startup_rejects_invalid_secrets_clients_and_policy(changes):
    with pytest.raises(ValueError):
        valid(**changes)


@pytest.mark.parametrize(
    "change",
    [
        {"redirect_uris": ["https://client.example/callback#fragment"]},
        {"redirect_uris": ["http://public.example/callback"]},
        {"scopes": ["catalog:read", "settings:write"]},
        {"client_secret": "plaintext"},
        {"client_secret_hash": "weak"},
    ],
)
def test_oauth_clients_reject_unsafe_redirects_management_scopes_and_plaintext_secrets(change):
    client = {
        "client_id": "client",
        "name": "Client",
        "redirect_uris": ["https://client.example/callback"],
        "scopes": ["catalog:read"],
        **change,
    }
    with pytest.raises(ValueError):
        valid(clients=[client])


def test_oauth_is_disabled_by_default_and_secret_key_is_redacted():
    assert McpOAuthSettings().enabled is False
    settings = valid()
    assert settings.encryption_key not in repr(settings)


def test_registered_client_can_request_knowledge_writes_with_explicit_read_dependencies():
    settings = valid(
        clients=[
            {
                "client_id": "review-client",
                "name": "Knowledge review client",
                "redirect_uris": ["https://client.example/callback"],
                "scopes": ["catalog:read", "catalog:write", "ingest:write"],
            }
        ]
    )
    assert settings.clients[0]["scopes"] == ["catalog:read", "catalog:write", "ingest:write"]
