# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from http_fixtures import client as client
from http_fixtures import oauth_client as oauth_client
from mcp.types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY
from test_mcp_http import HEADERS, call, create_pat
from test_mcp_legacy_sessions import initialize, legacy_call

from koinon.catalog.repositories import MembershipRepository

ADMIN_TOOLS = {"koinon_platform_health", "koinon_system_information"}


def tools(client, token, session=None):
    client.cookies.clear()
    version = "2025-11-25" if session else "2026-07-28"
    headers = {**HEADERS, "Authorization": "Bearer " + token, "MCP-Protocol-Version": version}
    if session:
        headers["MCP-Session-Id"] = session
    else:
        headers["MCP-Method"] = "tools/list"
    params = (
        {} if session else {"_meta": {PROTOCOL_VERSION_META_KEY: version, CLIENT_CAPABILITIES_META_KEY: {}}}
    )
    response = client.post(
        "/mcp", headers=headers, json={"jsonrpc": "2.0", "id": 22, "method": "tools/list", "params": params}
    )
    assert response.status_code == 200, response.text
    return response.json()["result"]["tools"]


@pytest.mark.parametrize("legacy", [False, True])
def test_only_unbounded_current_admin_pat_discovers_and_calls_platform_tools(client, legacy):
    admin = create_pat(client, scopes=["catalog:read", "audit:read"])["token"]
    ordinary = create_pat(client)["token"]
    session = initialize(client, admin) if legacy else None
    ordinary_session = initialize(client, ordinary) if legacy else None
    all_tools = tools(client, admin, session)
    regular = tools(client, ordinary, ordinary_session)
    assert {item["name"] for item in all_tools} >= ADMIN_TOOLS
    assert [item for item in all_tools if item["name"] not in ADMIN_TOOLS] == regular

    def invoke(token, name, arguments):
        return (
            legacy_call(client, token, session if token == admin else ordinary_session, name, arguments)
            if legacy
            else call(client, token, name, arguments)
        )

    value = invoke(admin, "koinon_system_information", {"tenant_id": "north"})
    assert value.status_code == 200 and not value.json()["result"]["isError"], value.text
    denied = invoke(ordinary, "koinon_system_information", {"tenant_id": "north"})
    assert denied.json()["result"]["isError"]
    assert "mcp/www_authenticate" not in denied.json()["result"].get("_meta", {})
    foreign = invoke(admin, "koinon_system_information", {"tenant_id": "south"})
    assert foreign.json()["result"]["isError"]


@pytest.mark.parametrize("legacy", [False, True])
def test_role_change_is_fresh_on_listing_and_call_without_reusing_session_authority(client, legacy):
    token = create_pat(client, scopes=["catalog:read", "audit:read"])["token"]
    session = initialize(client, token) if legacy else None
    assert {item["name"] for item in tools(client, token, session)} >= ADMIN_TOOLS

    async def downgrade():
        repository = client.native_app.state.context.get_bean(MembershipRepository)
        row = await repository.find_by_id("admin")
        row.role = "viewer"
        await repository.save(row)

    client.portal.call(downgrade)
    assert ADMIN_TOOLS.isdisjoint({item["name"] for item in tools(client, token, session)})
    result = (
        legacy_call(client, token, session, "koinon_system_information", {"tenant_id": "north"})
        if legacy
        else call(client, token, "koinon_system_information", {"tenant_id": "north"})
    )
    assert result.json()["result"]["isError"]


def test_workspace_oauth_never_advertises_platform_or_requests_broader_consent(oauth_client):
    from test_mcp_scope_upgrade import oauth_token

    token = oauth_token(oauth_client)
    assert ADMIN_TOOLS.isdisjoint({item["name"] for item in tools(oauth_client, token)})
    response = call(oauth_client, token, "koinon_system_information", {"tenant_id": "north"})
    assert response.json()["result"]["isError"]
    assert "mcp/www_authenticate" not in response.json()["result"].get("_meta", {})


@pytest.mark.parametrize("legacy", [False, True])
@pytest.mark.parametrize("change", ["scopes", "expired", "revoked"])
def test_credential_changes_are_current_on_discovery_and_execution(client, legacy, change):
    from datetime import UTC, datetime, timedelta

    from koinon.tokens.repositories import PersonalTokenRepository

    pat = create_pat(client, scopes=["catalog:read", "audit:read"])
    token = pat["token"]
    session = initialize(client, token) if legacy else None
    assert {item["name"] for item in tools(client, token, session)} >= ADMIN_TOOLS

    async def restrict():
        repository = client.native_app.state.context.get_bean(PersonalTokenRepository)
        row = await repository.find_by_id(pat["id"])
        if change == "scopes":
            row.scopes = ["catalog:read"]
        elif change == "expired":
            row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        else:
            row.revoked_at = datetime.now(UTC)
        await repository.save(row)

    client.portal.call(restrict)
    if change == "scopes" and legacy:
        stale = legacy_call(client, token, session, "koinon_system_information", {"tenant_id": "north"})
        assert stale.status_code == 404
        session = initialize(client, token)
    if change == "scopes":
        assert ADMIN_TOOLS.isdisjoint({item["name"] for item in tools(client, token, session)})
    result = (
        legacy_call(client, token, session, "koinon_system_information", {"tenant_id": "north"})
        if legacy
        else call(client, token, "koinon_system_information", {"tenant_id": "north"})
    )
    if change != "scopes":
        assert result.status_code == 401
    else:
        assert result.json()["result"]["isError"]


@pytest.mark.parametrize("unavailable", [None, "error"])
async def test_missing_or_failed_authority_resolver_hides_only_operational_tools_and_blocks_dispatch(
    unavailable,
):
    from types import SimpleNamespace

    from pyfly.mcp import McpServer

    from koinon.mcp.platform_tools import install_platform_visibility

    async def failing(raw):
        raise RuntimeError("private-authentication-details")

    server = McpServer("bounded-operational-test")
    install_platform_visibility(server, None if unavailable is None else failing)
    boundary = server.registry.middleware[0]
    existing = {"name": "koinon_context", "description": "existing"}
    dispatched = []

    async def next_handler(ctx):
        dispatched.append(ctx.method)
        return {
            "tools": [existing, {"name": "koinon_platform_health"}, {"name": "koinon_system_information"}]
        }

    context = SimpleNamespace(
        method="tools/list",
        params={},
        request=SimpleNamespace(headers={"authorization": "Bearer server-test-token"}),
    )
    result = await boundary(context, next_handler)
    assert result == {"tools": [existing]}
    assert result["tools"][0] is existing
    context.method = "tools/call"
    context.params = {"name": "koinon_platform_health"}
    denied = await boundary(context, next_handler)
    assert denied.is_error and dispatched == ["tools/list"]
    assert "private-authentication-details" not in denied.model_dump_json()


def test_admin_pat_tools_do_not_advertise_unavailable_oauth_audit_consent(oauth_client):
    token = create_pat(oauth_client, scopes=["catalog:read", "audit:read"])["token"]
    advertised = [item for item in tools(oauth_client, token) if item["name"] in ADMIN_TOOLS]
    assert len(advertised) == 2
    assert all("securitySchemes" not in item.get("_meta", {}) for item in advertised)
