# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from conftest import bearer
from pydantic import ValidationError
from test_mcp_oauth import authorize
from test_mcp_oauth import oauth as oauth

from koinon.mcp_applications.dtos import McpOAuthClientInput


def test_oauth_metadata_and_registration_never_offer_administrator_only_pat_scope(oauth):
    resource = oauth.get("/.well-known/oauth-protected-resource/mcp").json()
    authorization = oauth.get("/.well-known/oauth-authorization-server/oauth2/mcp").json()
    assert "audit:read" not in resource["scopes_supported"]
    assert resource["scopes_supported"] == authorization["scopes_supported"]
    assert len(resource["scopes_supported"]) == 8
    from koinon.mcp.server import TOOL_SCOPES
    from koinon.mcp_auth.settings import MCP_RESOURCE_SCOPES

    assert set(resource["scopes_supported"]) | {"audit:read"} == MCP_RESOURCE_SCOPES
    assert all(set(scopes) <= MCP_RESOURCE_SCOPES for scopes in TOOL_SCOPES.values())
    response = oauth.post(
        "/api/v1/tenants/north/mcp/oauth-clients",
        headers=bearer(),
        json={
            "name": "Invalid management scope",
            "client_type": "public",
            "redirect_uris": ["https://client.example/callback"],
            "scopes": ["catalog:read", "audit:read"],
        },
    )
    assert response.status_code == 422
    from koinon.mcp_auth.settings import McpOAuthSettings

    oauth.native_app.state.context.get_bean(McpOAuthSettings).clients[0]["scopes"].append("audit:read")
    denied = authorize(oauth, scope="catalog:read audit:read")
    assert denied.status_code == 400 and denied.json()["error"] == "invalid_scope"
    assert "request_id" not in denied.text
    with pytest.raises(ValidationError):
        McpOAuthClientInput(
            name="Invalid management scope",
            client_type="public",
            redirect_uris=["https://client.example/callback"],
            scopes=["catalog:read", "audit:read"],
        )
