# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from http_fixtures import ISSUER, bearer
from http_fixtures import client as client
from http_fixtures import oauth_client as oauth_client
from test_mcp_http import HEADERS, create_pat
from test_mcp_review_http import proposal


def initialize(client, token, *, apps=True):
    client.cookies.clear()
    response = client.post(
        "/mcp",
        headers={**HEADERS, "Authorization": "Bearer " + token},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "clientInfo": {"name": "controlled-apps-client", "version": "1"},
                "capabilities": {
                    "extensions": {"io.modelcontextprotocol/ui": {"mimeTypes": ["text/html;profile=mcp-app"]}}
                }
                if apps
                else {},
            },
        },
    )
    assert response.status_code == 200, response.text
    session = response.headers.get("mcp-session-id")
    assert session, "Legacy initialize must establish a bounded session"
    response = client.post(
        "/mcp",
        headers={
            **HEADERS,
            "Authorization": "Bearer " + token,
            "MCP-Session-Id": session,
            "MCP-Protocol-Version": "2025-11-25",
        },
        json={"jsonrpc": "2.0", "method": "notifications/initialized"},
    )
    assert response.status_code == 202, response.text
    return session


def legacy_call(client, token, session, name, arguments):
    client.cookies.clear()
    return client.post(
        "/mcp",
        headers={
            **HEADERS,
            "Authorization": "Bearer " + token,
            "MCP-Session-Id": session,
            "MCP-Protocol-Version": "2025-11-25",
        },
        json={
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
    )


def test_native_legacy_session_retains_apps_and_cannot_be_reused_by_another_credential(client):
    arguments = proposal(client)
    first = create_pat(client, scopes=["ingest:write"])
    second = create_pat(client, scopes=["ingest:write"])
    session = initialize(client, first["token"])
    result = legacy_call(client, first["token"], session, "koinon_stage_knowledge", arguments)
    assert result.status_code == 200, result.text
    value = result.json()["result"]
    assert value["isError"] is False and value["_meta"]["koinon/knowledgeReview"]["nonce"]
    assert value["structuredContent"]["review"]["review"]["owner_subject"] == ISSUER + "|admin"
    denied = legacy_call(client, second["token"], session, "koinon_stage_knowledge", arguments)
    assert denied.status_code == 404 and "koinon/knowledgeReview" not in denied.text
    assert client.delete("/api/v1/tokens/" + first["id"], headers=bearer()).status_code == 204
    assert legacy_call(client, first["token"], session, "koinon_context", {}).status_code == 401


def test_native_legacy_without_apps_leaves_no_proposal_or_private_nonce(client):
    from koinon.knowledge.external_reviews.repositories import ExternalReviewRepository

    arguments = proposal(client)
    token = create_pat(client, scopes=["ingest:write"])["token"]
    session = initialize(client, token, apps=False)
    result = legacy_call(client, token, session, "koinon_stage_knowledge", arguments)
    assert result.status_code == 200, result.text
    value = result.json()["result"]
    assert value["isError"] is True and "MCP Apps" in str(value["content"])
    assert "koinon/knowledgeReview" not in value.get("_meta", {})
    assert client.portal.call(client.native_app.state.context.get_bean(ExternalReviewRepository).count) == 0
    allowed = legacy_call(client, token, session, "koinon_context", {})
    assert allowed.status_code == 200 and allowed.json()["result"]["isError"] is False


def test_native_legacy_expiry_is_rechecked_after_initialization(client):
    from koinon.tokens.repositories import PersonalTokenRepository

    token = create_pat(client)
    session = initialize(client, token["token"])

    async def expire():
        repository = client.native_app.state.context.get_bean(PersonalTokenRepository)
        row = await repository.find_by_id(token["id"])
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await repository.save(row)

    client.portal.call(expire)
    assert legacy_call(client, token["token"], session, "koinon_context", {}).status_code == 401


@pytest.mark.parametrize("client", [{"max_sessions": 1, "session_idle_timeout_seconds": 30}], indirect=True)
def test_native_legacy_capacity_and_timeout_are_configured_and_bounded(client):
    from koinon.mcp.settings import McpSettings

    token = create_pat(client)["token"]
    initialize(client, token)
    client.cookies.clear()
    refused = client.post(
        "/mcp",
        headers={**HEADERS, "Authorization": "Bearer " + token},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "clientInfo": {"name": "second-owned-client", "version": "1"},
                "capabilities": {},
            },
        },
    )
    assert refused.status_code == 503
    configuration = client.native_app.state.context.get_bean(McpSettings)
    manager = client.native_app.state.mcp_server.session_manager
    assert manager.max_sessions == configuration.max_sessions == 1
    assert manager.session_idle_timeout == configuration.session_idle_timeout_seconds == 30


def test_native_legacy_oauth_application_can_stage_and_revocation_invalidates_session(oauth_client):
    from test_mcp_scope_upgrade import oauth_token

    from koinon.mcp_auth.settings import McpOAuthSettings

    values = proposal(oauth_client)
    settings = oauth_client.native_app.state.context.get_bean(McpOAuthSettings)
    settings.clients[0]["scopes"].extend(["catalog:write", "ingest:write"])
    token = oauth_token(oauth_client, scopes="ingest:write")
    session = initialize(oauth_client, token)
    response = legacy_call(oauth_client, token, session, "koinon_stage_knowledge", values)
    assert response.status_code == 200 and response.json()["result"]["isError"] is False
    apps = oauth_client.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    active = next(value for value in apps if value["status"] == "active")
    assert (
        oauth_client.delete("/api/v1/authorized-applications/" + active["id"], headers=bearer()).status_code
        == 204
    )
    assert legacy_call(oauth_client, token, session, "koinon_context", {}).status_code == 401


def test_native_legacy_current_role_is_checked_after_session_initialization(client):
    from koinon.catalog.repositories import MembershipRepository

    values = proposal(client)
    token = create_pat(client, scopes=["ingest:write"])["token"]
    session = initialize(client, token)

    async def downgrade():
        repository = client.native_app.state.context.get_bean(MembershipRepository)
        row = await repository.find_by_id("admin")
        row.role = "viewer"
        await repository.save(row)

    client.portal.call(downgrade)
    response = legacy_call(client, token, session, "koinon_stage_knowledge", values)
    assert response.status_code == 200 and response.json()["result"]["isError"] is True
    assert "koinon/knowledgeReview" not in response.json()["result"].get("_meta", {})
