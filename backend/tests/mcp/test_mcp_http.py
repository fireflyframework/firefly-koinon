# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from http_fixtures import bearer
from http_fixtures import client as client
from mcp.types import CLIENT_CAPABILITIES_META_KEY, PROTOCOL_VERSION_META_KEY

from koinon.mcp.server import REVIEW_TOOLS

HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


def call(client, token, name, arguments=None, **headers):
    client.cookies.clear()
    return client.post(
        "/mcp",
        headers={
            **HEADERS,
            "Authorization": "Bearer " + token,
            "MCP-Protocol-Version": "2026-07-28",
            "MCP-Method": "tools/call",
            "MCP-Name": name,
            **headers,
        },
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments or {},
                "_meta": {
                    PROTOCOL_VERSION_META_KEY: "2026-07-28",
                    CLIENT_CAPABILITIES_META_KEY: {
                        "extensions": {
                            "io.modelcontextprotocol/ui": {"mimeTypes": ["text/html;profile=mcp-app"]}
                        }
                    }
                    if name in REVIEW_TOOLS
                    else {},
                },
            },
        },
    )


def create_pat(client, subject="admin", scopes=None, **values):
    response = client.post(
        "/api/v1/tokens",
        headers=bearer(subject),
        json={
            "name": "Local MCP test",
            "tenant_id": "north",
            "scopes": scopes or ["catalog:read"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            **values,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_mcp_requires_explicit_bearer_and_rejects_api_jwt_cookies_and_untrusted_origins(client):
    response = client.post("/mcp", headers=HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert response.status_code == 401
    client.cookies.clear()
    assert client.post("/mcp", headers={**HEADERS, **bearer()}, json={}).status_code == 401
    token = create_pat(client)["token"]
    assert call(client, token, "koinon_context", Cookie="session=browser").status_code == 400
    assert call(client, token, "koinon_context", Origin="https://attacker.example").status_code == 403
    assert call(client, token, "koinon_context", Host="attacker.example").status_code == 421


def test_mcp_pat_uses_canonical_permissions_and_revocation(client):
    token = create_pat(client)
    response = call(client, token["token"], "koinon_list", {"tenant_id": "north"})
    assert response.status_code == 200, response.text
    assert "set-cookie" not in response.headers
    assert response.headers["cache-control"] == "private, no-store"
    assert response.json()["result"]["isError"] is False
    denied = call(client, token["token"], "koinon_list", {"tenant_id": "south"})
    assert denied.status_code == 200
    assert denied.json()["result"]["isError"] is True
    assert "403" in str(denied.json())
    assert client.delete("/api/v1/tokens/" + token["id"], headers=bearer()).status_code == 204
    assert call(client, token["token"], "koinon_context").status_code == 401


def test_mcp_current_membership_is_rechecked_after_pat_issue(client):
    token = create_pat(client)
    assert (
        call(client, token["token"], "koinon_list", {"tenant_id": "north"}).json()["result"]["isError"]
        is False
    )

    async def revoke():
        from koinon.catalog.repositories import MembershipRepository

        repository = client.native_app.state.context.get_bean(MembershipRepository)
        await repository.delete_by_id("admin")

    client.portal.call(revoke)
    denied = call(client, token["token"], "koinon_list", {"tenant_id": "north"})
    assert denied.status_code == 200
    assert denied.json()["result"]["isError"] is True


def test_source_fetch_preserves_canonical_identity_and_denies_other_workspace(client):
    token = create_pat(client, workspace_ids=[client.workspace_id])["token"]
    canonical = client.get(
        "/api/v1/tenants/north/catalog/" + client.workspace_id,
        headers={"Authorization": "Bearer " + token},
    )
    fetched = call(client, token, "koinon_fetch", {"tenant_id": "north", "source_id": client.workspace_id})
    assert fetched.status_code == 200, fetched.text
    result = fetched.json()["result"]["structuredContent"]
    assert result.pop("read_receipt") == {
        "status": "not_recorded",
        "reason": "catalog_is_not_source_evidence",
        "sources": [],
    }
    assert result == canonical.json()
    other = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer(),
        json={"kind": "workspace", "name": "Other workspace"},
    ).json()["id"]
    denied = call(client, token, "koinon_fetch", {"tenant_id": "north", "source_id": other})
    assert denied.json()["result"]["isError"] is True
    assert "403" in str(denied.json())


def test_search_and_query_do_not_bypass_canonical_operation_scopes(client):
    token = create_pat(client)["token"]
    for name, arguments in (
        (
            "koinon_search",
            {"tenant_id": "north", "workspace_id": client.workspace_id, "question": "Private facts"},
        ),
        ("koinon_query", {"tenant_id": "north", "dataset_id": client.workspace_id, "sql": "SELECT 1"}),
    ):
        denied = call(client, token, name, arguments)
        assert denied.status_code == 200, denied.text
        assert denied.json()["result"]["isError"] is True
        assert "403" in str(denied.json())


def test_answer_audit_keeps_unknown_provenance_and_rejects_another_user(client, monkeypatch):
    import runpy
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "web"))
    seed = runpy.run_path(str(Path(__file__).parents[1] / "web" / "test_chat_sse.py"))["seed"]
    run_id = client.portal.call(seed, client.native_app.state.context)
    owner = create_pat(client, scopes=["chat:use"])["token"]
    other = create_pat(client, subject="editor", scopes=["chat:use"])["token"]
    arguments = {"tenant_id": "north", "run_id": run_id}
    response = call(client, owner, "koinon_answer_audit", arguments)
    assert response.status_code == 200, response.text
    result = response.json()["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["provenance_status"] == "not_recorded"
    assert result["structuredContent"]["source_provenance_complete"] is None
    denied = call(client, other, "koinon_answer_audit", arguments)
    assert denied.json()["result"]["isError"] is True
    assert "403" in str(denied.json())


def test_workspace_membership_revocation_applies_to_existing_mcp_pat(client):
    async def restrict_to_workspace():
        from koinon.catalog.repositories import MembershipRepository

        repository = client.native_app.state.context.get_bean(MembershipRepository)
        row = await repository.find_by_id("viewer")
        row.workspace_id = client.workspace_id
        await repository.save(row)

    client.portal.call(restrict_to_workspace)
    token = create_pat(client, subject="viewer", workspace_ids=[client.workspace_id])["token"]
    arguments = {"tenant_id": "north", "source_id": client.workspace_id}
    assert call(client, token, "koinon_fetch", arguments).json()["result"]["isError"] is False

    async def revoke_workspace():
        from koinon.catalog.repositories import MembershipRepository

        repository = client.native_app.state.context.get_bean(MembershipRepository)
        await repository.delete_by_id("viewer")

    client.portal.call(revoke_workspace)
    denied = call(client, token, "koinon_fetch", arguments)
    assert denied.json()["result"]["isError"] is True
    assert "403" in str(denied.json())


def test_official_client_initializes_discovers_and_calls_actual_application(client):
    from test_mcp_server import protocol

    token = create_pat(client)["token"]

    async def connect():
        async with protocol(client.native_app, {"Authorization": "Bearer " + token}) as session:
            tools = await session.list_tools()
            assert "koinon_fetch" in {tool.name for tool in tools.tools}
            result = await session.call_tool(
                "koinon_fetch", {"tenant_id": "north", "source_id": client.workspace_id}
            )
            assert not result.is_error
            assert result.structured_content["id"] == client.workspace_id

    client.portal.call(connect)


def test_mcp_bounds_request_body_without_invoking_a_tool(client):
    token = create_pat(client)["token"]
    client.cookies.clear()
    response = client.post(
        "/mcp", headers={**HEADERS, "Authorization": "Bearer " + token}, content=b"x" * 131073
    )
    assert response.status_code == 413, response.text
    assert "set-cookie" not in response.headers


def test_catalog_tool_browses_sources_tables_and_all_canonical_kinds(client):
    token = create_pat(client)["token"]
    for kind in ("corpus", "source", "table", "chunk", "index_version", "query_session"):
        response = call(client, token, "koinon_list", {"tenant_id": "north", "kind": kind})
        assert response.status_code == 200, response.text
        assert response.json()["result"]["isError"] is False, response.text
        assert response.json()["result"]["structuredContent"]["items"] == []
