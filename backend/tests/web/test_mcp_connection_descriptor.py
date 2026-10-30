# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import bearer


def test_connection_descriptor_is_typed_and_disabled_without_an_operator_endpoint(client):
    response = client.get("/api/v1/mcp/connection", headers=bearer())
    assert response.status_code == 200
    value = response.json()
    assert value["enabled"] is False and value["endpoint"] is None
    assert value["transport"] == "streamable-http"
    assert value["client_acceptance"] == "not_verified"
    assert value["review"]["mechanism"] == "mcp_apps"
    assert value["review"]["resource_uri"] == "ui://koinon/knowledge-review"
    assert value["review"]["external_redirect"] is False


def test_connection_descriptor_uses_trusted_configuration_not_request_authority(client):
    from koinon.mcp.settings import McpSettings

    settings = client.native_app.state.context.get_bean(McpSettings)
    settings.enabled = True
    settings.public_url = "https://organization.example.test/mcp"
    response = client.get(
        "/api/v1/mcp/connection",
        headers={**bearer(), "X-Forwarded-Host": "attacker.example", "X-Forwarded-Proto": "http"},
    )
    assert response.status_code == 200
    value = response.json()
    assert value["endpoint"] == "https://organization.example.test/mcp"
    assert "personal_token" in value["authentication"]
    assert not any("attacker.example" in str(item) for item in value.values())
    assert all("nonce" not in tool for tool in value["tools"])


def test_connection_descriptor_requires_authenticated_identity(client):
    assert client.get("/api/v1/mcp/connection").status_code == 401
