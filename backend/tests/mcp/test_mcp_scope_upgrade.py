# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

from http_fixtures import ISSUER, bearer
from http_fixtures import oauth_client as oauth_client
from test_mcp_http import call
from test_mcp_server import protocol


def oauth_token(client, subject="admin", scopes="catalog:read"):
    from koinon.mcp_auth.service import McpOAuthService

    service = client.native_app.state.context.get_bean(McpOAuthService)
    verifier = "s" * 43
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": "scope-client",
        "redirect_uri": "https://client.example/callback",
        "response_type": "code",
        "resource": "http://127.0.0.1:18781/mcp",
        "scope": scopes,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    request_id, _, _, _ = client.portal.call(service.begin, ISSUER + "|" + subject, params)
    redirect = client.portal.call(
        service.consent, ISSUER + "|" + subject, request_id, "allow", "north", client.workspace_id
    )
    code = parse_qs(urlsplit(redirect).query)["code"][0]
    return client.portal.call(
        service.exchange,
        {
            "grant_type": "authorization_code",
            "client_id": "scope-client",
            "code": code,
            "redirect_uri": "https://client.example/callback",
            "resource": params["resource"],
            "code_verifier": verifier,
        },
    )["access_token"]


def test_official_tool_discovery_declares_actual_operation_scopes(oauth_client):
    token = oauth_token(oauth_client)

    async def verify():
        async with protocol(oauth_client.native_app, {"Authorization": "Bearer " + token}) as session:
            tools = {tool.name: tool for tool in (await session.list_tools()).tools}
            assert tools["koinon_search"].meta["securitySchemes"] == [
                {"type": "oauth2", "scopes": ["catalog:read", "knowledge:search"]}
            ]
            assert tools["koinon_query"].meta["securitySchemes"] == [
                {"type": "oauth2", "scopes": ["catalog:read", "query:execute"]}
            ]
            assert tools["koinon_fetch"].meta["securitySchemes"] == [
                {"type": "oauth2", "scopes": ["catalog:read"]}
            ]

    oauth_client.portal.call(verify)


def test_actual_scope_denial_triggers_official_client_challenge_and_upgrade_works(oauth_client):
    token = oauth_token(oauth_client)
    arguments = {"tenant_id": "north", "workspace_id": oauth_client.workspace_id, "question": "Facts"}

    async def verify():
        async with protocol(oauth_client.native_app, {"Authorization": "Bearer " + token}) as session:
            result = await session.call_tool("koinon_search", arguments)
            assert result.is_error
            challenges = result.meta["mcp/www_authenticate"]
            assert len(challenges) == 1
            assert 'error="insufficient_scope"' in challenges[0]
            assert 'error_description="' in challenges[0]
            assert 'scope="catalog:read knowledge:search"' in challenges[0]
            assert (
                'resource_metadata="http://127.0.0.1:18781/.well-known/oauth-protected-resource/mcp"'
                in challenges[0]
            )
            assert token not in str(result)

    oauth_client.portal.call(verify)
    upgraded = oauth_token(oauth_client, scopes="catalog:read knowledge:search")
    response = call(oauth_client, upgraded, "koinon_search", arguments)
    assert response.json()["result"]["isError"] is False
    assert response.json()["result"]["structuredContent"] == {"hits": []}


def test_foreign_workspace_and_current_role_denials_do_not_prompt_scope_upgrade(oauth_client):
    token = oauth_token(oauth_client)
    other = oauth_client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer(),
        json={"kind": "workspace", "name": "Foreign workspace"},
    ).json()["id"]
    denied = call(
        oauth_client,
        token,
        "koinon_search",
        {
            "tenant_id": "north",
            "workspace_id": other,
            "question": "Facts",
        },
    ).json()["result"]
    assert denied["isError"] is True
    assert "mcp/www_authenticate" not in denied.get("_meta", {})
    viewer = oauth_token(oauth_client, subject="viewer")
    denied = call(
        oauth_client,
        viewer,
        "koinon_query",
        {
            "tenant_id": "north",
            "dataset_id": oauth_client.workspace_id,
            "sql": "SELECT 1",
        },
    ).json()["result"]
    assert denied["isError"] is True
    assert "mcp/www_authenticate" not in denied.get("_meta", {})


def test_client_without_requested_operation_scope_does_not_loop_reauthorization(oauth_client):
    from koinon.mcp_auth.settings import McpOAuthSettings

    token = oauth_token(oauth_client)
    settings = oauth_client.native_app.state.context.get_bean(McpOAuthSettings)
    settings.clients[0]["scopes"] = ["catalog:read"]
    denied = call(
        oauth_client,
        token,
        "koinon_search",
        {
            "tenant_id": "north",
            "workspace_id": oauth_client.workspace_id,
            "question": "Facts",
        },
    ).json()["result"]
    assert denied["isError"] is True
    assert "mcp/www_authenticate" not in denied.get("_meta", {})


def test_canonical_scope_signal_preserves_role_workspace_and_projection_denials(oauth_client):
    from koinon.mcp_auth.service import McpOAuthService

    service = oauth_client.native_app.state.context.get_bean(McpOAuthService)
    token = oauth_token(oauth_client)
    pat = oauth_client.portal.call(service.canonical_bearer, token)
    headers = {"Authorization": "Bearer " + pat}
    scope_denied = oauth_client.post(
        "/api/v1/tenants/north/search",
        headers=headers,
        json={"workspace_id": oauth_client.workspace_id, "question": "Facts"},
    )
    assert scope_denied.status_code == 401
    assert (
        call(
            oauth_client,
            token,
            "koinon_search",
            {"tenant_id": "north", "workspace_id": oauth_client.workspace_id, "question": "Facts"},
        ).json()["result"]["isError"]
        is True
    )
    import pytest
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied

    async def projected_denial():
        context = await service.authenticate(token)
        with SecurityContextHolder.using(context):
            await service.catalog.authorize(ISSUER + "|admin", "north", "query:execute")

    with pytest.raises(AccessDenied) as error:
        oauth_client.portal.call(projected_denial)
    assert error.value.code == "ACCESS_DENIED"


def test_scope_upgrade_does_not_request_permissions_the_token_already_holds(oauth_client):
    from koinon.mcp_auth.service import McpOAuthService

    token = oauth_token(oauth_client)
    service = oauth_client.native_app.state.context.get_bean(McpOAuthService)
    assert oauth_client.portal.call(service.can_request_scopes, token, ("catalog:read",)) is False
    assert (
        oauth_client.portal.call(service.can_request_scopes, token, ("catalog:read", "knowledge:search"))
        is True
    )


def test_asset_restricted_grant_never_becomes_a_scope_upgrade_signal(oauth_client):
    from test_mcp_http import create_pat

    parent = oauth_client.workspace_id
    for kind in ("project", "collection", "source", "document"):
        response = oauth_client.post(
            "/api/v1/tenants/north/catalog",
            headers=bearer(),
            json={"kind": kind, "name": "Restricted " + kind, "parent_id": parent},
        )
        assert response.status_code == 201, response.text
        parent = response.json()["id"]
    token = create_pat(oauth_client, asset_ids=[parent])["token"]
    response = oauth_client.post(
        "/api/v1/tenants/north/query",
        headers={"Authorization": "Bearer " + token},
        json={"dataset_id": parent, "sql": "SELECT 1"},
    )
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"
