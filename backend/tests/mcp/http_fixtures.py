# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reuse the canonical local HTTP fixture, enabling only the MCP transport."""

import runpy
from pathlib import Path

import pytest

_fixture = runpy.run_path(str(Path(__file__).parents[1] / "web" / "conftest.py"))
bearer = _fixture["bearer"]
ISSUER = _fixture["ISSUER"]


def configured_client(tmp_path, monkeypatch, request, *, oauth=False):
    import koinon.app

    original = koinon.app.create_application

    def enabled(config):
        config["koinon"]["mcp"] = {
            "enabled": True,
            "public_url": "http://127.0.0.1:18781/mcp",
            "allowed_hosts": ["testserver"],
        }
        if oauth:
            from cryptography.fernet import Fernet

            config["koinon"]["mcp"]["oauth"] = {
                "enabled": True,
                "encryption_key": Fernet.generate_key().decode(),
                "clients": [
                    {
                        "client_id": "scope-client",
                        "name": "Scope Client",
                        "redirect_uris": ["https://client.example/callback"],
                        "scopes": ["catalog:read", "knowledge:search", "query:execute", "chat:use"],
                    }
                ],
            }
        config["koinon"]["knowledge"] = {"enabled": True}
        return original(config)

    monkeypatch.setattr(koinon.app, "create_application", enabled)
    yield from _fixture["client"].__wrapped__(tmp_path, monkeypatch, request)


@pytest.fixture
def client(tmp_path, monkeypatch, request):
    yield from configured_client(tmp_path, monkeypatch, request)


@pytest.fixture
def oauth_client(tmp_path, monkeypatch, request):
    yield from configured_client(tmp_path, monkeypatch, request, oauth=True)
