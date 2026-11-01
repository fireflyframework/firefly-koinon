# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native SQL/HTTP connection ownership and application credential separation."""

from urllib.parse import parse_qs, urlsplit

from conftest import bearer
from test_mcp_oauth import consent, exchange
from test_mcp_oauth import oauth as oauth


def connected(client):
    response = exchange(client, parse_qs(urlsplit(consent(client).headers["location"]).query)["code"][0])
    assert response.status_code == 200, response.text
    assert "refresh_token" not in response.json()
    return response.json()["access_token"]


def test_authorized_application_is_a_private_owner_connection_not_a_personal_token(oauth):
    opaque = connected(oauth)
    response = oauth.get("/api/v1/authorized-applications", headers=bearer())
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 1 and page["page_size"] == 25
    grant = page["items"][0]
    assert set(grant) == {
        "id",
        "client_id",
        "name",
        "resource",
        "tenant_id",
        "tenant_name",
        "workspace_id",
        "workspace_name",
        "scopes",
        "status",
        "connected_at",
        "expires_at",
        "last_used_at",
        "revoked_at",
    }
    assert grant["name"] == "Test Chat Client"
    assert grant["client_id"] == "test-chat-client"
    assert grant["workspace_id"] == oauth.workspace_id and grant["workspace_name"] == "Research"
    assert grant["tenant_name"] == "North" and grant["scopes"] == ["catalog:read"]
    assert grant["status"] == "active" and grant["revoked_at"] is None
    assert opaque not in str(page) and "koinon_pat_" not in str(page)
    assert oauth.get("/api/v1/authorized-applications/" + grant["id"], headers=bearer()).json() == grant
    assert oauth.get("/api/v1/tokens", headers=bearer()).json()["items"] == []
    assert (
        oauth.get("/api/v1/authorized-applications/" + grant["id"], headers=bearer("viewer")).status_code
        == 404
    )


def test_reconnect_replaces_only_the_active_same_application_space(oauth):
    import pytest
    from pyfly.kernel import UnauthorizedException

    from koinon.mcp_auth.service import McpOAuthService

    first = connected(oauth)
    first_row = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]
    second = connected(oauth)
    rows = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    assert len(rows) == 2
    previous = next(row for row in rows if row["id"] == first_row["id"])
    assert previous["status"] == "revoked"
    assert sum(row["status"] == "active" for row in rows) == 1
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    with pytest.raises(UnauthorizedException):
        oauth.portal.call(service.canonical_bearer, first)
    assert oauth.portal.call(service.canonical_bearer, second)


def mcp_call(client, opaque, tenant="north"):
    from copy import copy

    cookies = [copy(cookie) for cookie in client.cookies.jar]
    client.cookies.clear()
    headers = {"Authorization": "Bearer " + opaque, "Accept": "application/json, text/event-stream"}
    session = None
    try:
        opened = client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "owned-application-test", "version": "1"},
                },
            },
        )
        if opened.status_code != 200:
            return opened
        session = opened.headers["mcp-session-id"]
        headers.update({"MCP-Session-Id": session, "MCP-Protocol-Version": "2025-11-25"})
        initialized = client.post(
            "/mcp", headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}
        )
        assert initialized.status_code == 202
        return client.post(
            "/mcp",
            headers=headers,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "koinon_list", "arguments": {"tenant_id": tenant}},
            },
        )
    finally:
        if session is not None:
            client.delete("/mcp", headers=headers)
        for cookie in cookies:
            client.cookies.jar.set_cookie(cookie)


def test_disconnect_fences_live_mcp_and_never_exposes_application_credentials_to_pat_management(oauth):
    from koinon.mcp_auth.service import McpOAuthService

    opaque = connected(oauth)
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    private = oauth.portal.call(service.canonical_bearer, opaque)
    identifier = private.split("_pat_")[1].split(".")[0]
    assert oauth.delete("/api/v1/tokens/" + identifier, headers=bearer()).status_code == 403
    assert oauth.get("/api/v1/context", headers={"Authorization": "Bearer " + private}).status_code == 401
    assert mcp_call(oauth, private).status_code == 401
    assert mcp_call(oauth, opaque).json()["result"]["isError"] is False
    row = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]
    assert (
        oauth.delete("/api/v1/authorized-applications/" + row["id"], headers=bearer("viewer")).status_code
        == 404
    )
    assert oauth.delete("/api/v1/authorized-applications/" + row["id"], headers=bearer()).status_code == 204
    assert mcp_call(oauth, opaque).status_code == 401
    assert oauth.delete("/api/v1/authorized-applications/" + row["id"], headers=bearer()).status_code == 204


def test_pats_cannot_manage_connections_or_choose_the_application_purpose(oauth):
    from datetime import UTC, datetime, timedelta

    values = {
        "name": "Manual token",
        "tenant_id": "north",
        "scopes": ["catalog:read"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    rejected = oauth.post("/api/v1/tokens", headers=bearer(), json={**values, "purpose": "application"})
    assert rejected.status_code in {400, 422}
    token = oauth.post("/api/v1/tokens", headers=bearer(), json=values).json()["token"]
    response = oauth.get("/api/v1/authorized-applications", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 403 and response.json()["code"] == "INTERACTIVE_IDENTITY_REQUIRED"


def test_replacement_failure_rolls_back_code_grant_and_private_credential(oauth, monkeypatch):
    from koinon.catalog.errors import AccessDenied
    from koinon.mcp_auth.service import McpOAuthService

    opaque = connected(oauth)
    old = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]
    code = parse_qs(urlsplit(consent(oauth).headers["location"]).query)["code"][0]
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    original = service.tokens.issue_application

    async def fail(*args, **kwargs):
        raise AccessDenied("Synthetic issue failure", code="ACCESS_DENIED")

    monkeypatch.setattr(service.tokens, "issue_application", fail)
    assert exchange(oauth, code).status_code == 403
    assert oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"] == [old]

    async def counts():
        return len(await service.applications.repository.find_all()), len(
            await service.tokens.repository.find_all(purpose="application")
        )

    assert oauth.portal.call(counts) == (1, 1)
    assert oauth.portal.call(service.canonical_bearer, opaque)
    monkeypatch.setattr(service.tokens, "issue_application", original)
    assert exchange(oauth, code).status_code == 200


def test_connections_survive_a_fresh_application_context_and_revocation_crosses_instances(oauth):
    from starlette.testclient import TestClient

    from koinon.mcp_auth.service import McpOAuthService

    opaque = connected(oauth)
    original = oauth.native_app.state.context.get_bean(McpOAuthService)
    app = oauth.application_factory(oauth.native_app.state.context.config.to_dict())
    with TestClient(app) as restarted:
        row = restarted.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]
        service = app.state.context.get_bean(McpOAuthService)
        assert service is not original
        assert (
            restarted.get("/api/v1/authorized-applications/" + row["id"], headers=bearer()).status_code == 200
        )
        assert mcp_call(restarted, opaque).json()["result"]["isError"] is False
        assert (
            restarted.delete("/api/v1/authorized-applications/" + row["id"], headers=bearer()).status_code
            == 204
        )
        assert mcp_call(oauth, opaque).status_code == 401


def authorization_code(client, scope="catalog:read", workspace=None):
    import re

    from test_mcp_oauth import authorize

    page = authorize(client, scope=scope)
    assert page.status_code == 200, page.text
    identifier = re.search(r'name="request_id" value="([^"]+)"', page.text)[1]
    reply = client.post(
        "/oauth2/mcp/authorize",
        data={
            "request_id": identifier,
            "decision": "allow",
            "tenant_id": "north",
            "workspace_id": workspace or client.workspace_id,
            "_csrf": client.cookies.get("XSRF-TOKEN"),
        },
        follow_redirects=False,
    )
    assert reply.status_code == 302, reply.text
    return parse_qs(urlsplit(reply.headers["location"]).query)["code"][0]


def test_scope_upgrade_replaces_exact_scopes_without_touching_another_space(oauth):
    first = connected(oauth)
    other = oauth.post(
        "/api/v1/tenants/north/catalog", headers=bearer(), json={"kind": "workspace", "name": "Other space"}
    ).json()["id"]
    other_token = exchange(oauth, authorization_code(oauth, workspace=other)).json()["access_token"]
    upgraded = exchange(oauth, authorization_code(oauth, scope="catalog:read knowledge:search")).json()[
        "access_token"
    ]
    rows = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    assert len(rows) == 3
    active = [row for row in rows if row["status"] == "active"]
    assert len(active) == 2
    assert next(row for row in active if row["workspace_id"] == oauth.workspace_id)["scopes"] == [
        "catalog:read",
        "knowledge:search",
    ]
    assert next(row for row in active if row["workspace_id"] == other)["scopes"] == ["catalog:read"]
    assert mcp_call(oauth, first).status_code == 401
    assert mcp_call(oauth, other_token).json()["result"]["isError"] is False
    assert mcp_call(oauth, upgraded).json()["result"]["isError"] is False


def test_owner_only_bounded_pages_status_and_separate_application_quota(oauth):
    from datetime import UTC, datetime, timedelta

    from koinon.tokens.settings import TokenSettings

    settings = oauth.native_app.state.context.get_bean(TokenSettings)
    settings.max_active_per_user = 1
    values = {
        "name": "Personal only",
        "tenant_id": "north",
        "scopes": ["catalog:read"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    assert oauth.post("/api/v1/tokens", headers=bearer(), json=values).status_code == 201
    connected(oauth)
    assert oauth.get("/api/v1/tokens", headers=bearer()).json()["total"] == 1
    settings.max_active_applications_per_user = 1
    assert exchange(oauth, authorization_code(oauth)).status_code == 200
    other = oauth.post(
        "/api/v1/tenants/north/catalog", headers=bearer(), json={"kind": "workspace", "name": "Second space"}
    ).json()["id"]
    code = authorization_code(oauth, workspace=other)
    assert exchange(oauth, code).status_code == 400
    rows = oauth.get(
        "/api/v1/authorized-applications",
        headers=bearer(),
        params={"status": "active", "page_size": 1, "sort": "name", "order": "asc", "q": "Test Chat"},
    ).json()
    assert rows["total"] == 1 and len(rows["items"]) == 1
    for params in ({"page_size": 101}, {"q": "x" * 256}, {"status": "unknown"}, {"sort": "token_hash"}):
        assert (
            oauth.get("/api/v1/authorized-applications", headers=bearer(), params=params).status_code == 400
        )
    assert oauth.get("/api/v1/authorized-applications", headers=bearer("viewer")).json()["total"] == 0


def test_expiry_client_registration_and_binding_are_rechecked_without_refresh(oauth):
    import json
    from datetime import UTC, datetime, timedelta

    import pytest
    from cryptography.fernet import Fernet
    from pyfly.kernel import UnauthorizedException

    from koinon.mcp_auth.service import MCP_PREFIX, McpOAuthService

    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    opaque = connected(oauth)
    row = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]
    fernet = Fernet(service.settings.encryption_key.encode())
    payload = json.loads(fernet.decrypt(opaque[len(MCP_PREFIX) :].encode()))
    for key, value in [
        ("grant_id", "missing"),
        ("client_id", "unknown"),
        ("aud", "https://other.example/mcp"),
    ]:
        bad = MCP_PREFIX + fernet.encrypt(json.dumps({**payload, key: value}).encode()).decode()
        with pytest.raises(UnauthorizedException):
            oauth.portal.call(service.canonical_bearer, bad)
    service.settings.clients[0]["scopes"] = ["knowledge:search"]
    with pytest.raises(UnauthorizedException):
        oauth.portal.call(service.canonical_bearer, opaque)
    service.settings.clients[0]["scopes"] = ["catalog:read", "knowledge:search"]

    async def expire():
        grant = await service.applications.repository.find_by_id(row["id"])
        grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await service.applications.repository.save(grant)

    oauth.portal.call(expire)
    assert (
        oauth.get("/api/v1/authorized-applications/" + row["id"], headers=bearer()).json()["status"]
        == "expired"
    )
    assert mcp_call(oauth, opaque).status_code == 401


def test_concurrent_reconnects_leave_one_live_connection(oauth):
    import asyncio

    from pyfly.kernel import UnauthorizedException

    from koinon.mcp_auth.service import McpOAuthService

    codes = [authorization_code(oauth), authorization_code(oauth)]
    service = oauth.native_app.state.context.get_bean(McpOAuthService)

    async def compete():
        async def issue(code):
            return await service.exchange(
                {
                    "grant_type": "authorization_code",
                    "client_id": "test-chat-client",
                    "code": code,
                    "redirect_uri": "https://client.example/callback",
                    "code_verifier": "v" * 43,
                    "resource": service.mcp.public_url,
                }
            )

        return await asyncio.gather(*(issue(code) for code in codes))

    replies = oauth.portal.call(compete)
    rows = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    assert len(rows) == 2 and sum(row["status"] == "active" for row in rows) == 1
    accepted = 0
    for reply in replies:
        try:
            oauth.portal.call(service.canonical_bearer, reply["access_token"])
            accepted += 1
        except UnauthorizedException:
            pass
    assert accepted == 1


def test_failure_after_private_credential_write_preserves_previous_connection_and_code(oauth, monkeypatch):
    from koinon.catalog.errors import AccessDenied
    from koinon.mcp_auth.service import McpOAuthService

    old = connected(oauth)
    code = authorization_code(oauth)
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    original = service.catalog._audit

    async def fail(subject, tenant, action, *args, **kwargs):
        if action == "application.connected":
            raise AccessDenied("Synthetic final audit failure", code="ACCESS_DENIED")
        return await original(subject, tenant, action, *args, **kwargs)

    monkeypatch.setattr(service.catalog, "_audit", fail)
    assert exchange(oauth, code).status_code == 403

    async def retained():
        applications = await service.applications.repository.find_all()
        credentials = await service.tokens.repository.find_all(purpose="application")
        return len(applications), len(credentials), applications[0].revoked_at, credentials[0].revoked_at

    assert oauth.portal.call(retained) == (1, 1, None, None)
    assert oauth.portal.call(service.canonical_bearer, old)
    monkeypatch.setattr(service.catalog, "_audit", original)
    assert exchange(oauth, code).status_code == 200


def test_connection_use_is_coarsened_and_application_credentials_cannot_be_cloned_or_widened(oauth):
    from datetime import UTC, datetime, timedelta

    import pytest
    from pyfly.kernel import InvalidRequestException

    from koinon.catalog.errors import AccessDenied
    from koinon.mcp_auth.service import McpOAuthService

    opaque = connected(oauth)
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    first = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]
    assert first["last_used_at"] is None
    oauth.portal.call(service.canonical_bearer, opaque)
    used = oauth.get("/api/v1/authorized-applications/" + first["id"], headers=bearer()).json()
    oauth.portal.call(service.canonical_bearer, opaque)
    assert (
        oauth.get("/api/v1/authorized-applications/" + first["id"], headers=bearer()).json()["last_used_at"]
        == used["last_used_at"]
    )
    values = {
        "name": first["name"],
        "tenant_id": "north",
        "workspace_ids": [oauth.workspace_id],
        "scopes": first["scopes"],
        "expires_at": datetime.now(UTC) + timedelta(minutes=10),
    }

    async def clone():
        return await service.tokens.issue_application(
            "https://identity.example.test/realms/koinon|admin", values, first["id"]
        )

    with pytest.raises(InvalidRequestException):
        oauth.portal.call(clone)
    values["scopes"] = ["catalog:read", "knowledge:search"]
    with pytest.raises(AccessDenied):
        oauth.portal.call(clone)


def test_application_authentication_rolls_back_both_last_use_updates_on_failure(oauth, monkeypatch):
    import pytest

    from koinon.mcp_auth.service import McpOAuthService

    opaque = connected(oauth)
    service = oauth.native_app.state.context.get_bean(McpOAuthService)
    raw = oauth.portal.call(service.canonical_bearer, opaque)
    identifier = oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"][0]["id"]

    async def reset():
        credential = (await service.tokens.repository.find_all(authorized_application_id=identifier))[0]
        application = await service.applications.repository.find_by_id(identifier)
        credential.last_used_at = application.last_used_at = None
        await service.tokens.repository.save(credential)
        await service.applications.repository.save(application)

    oauth.portal.call(reset)

    async def fail(identifier):
        raise RuntimeError("Synthetic last-use failure")

    monkeypatch.setattr(service.applications.repository, "touch", fail)

    async def authenticate():
        return await service.tokens.authenticate(raw, purpose="application", application_id=identifier)

    with pytest.raises(RuntimeError, match="Synthetic last-use failure"):
        oauth.portal.call(authenticate)

    async def timestamps():
        credential = (await service.tokens.repository.find_all(authorized_application_id=identifier))[0]
        application = await service.applications.repository.find_by_id(identifier)
        return credential.last_used_at, application.last_used_at

    assert oauth.portal.call(timestamps) == (None, None)


def test_legacy_incomplete_consent_code_requires_reconnect_without_partial_issuance(oauth):
    from koinon.mcp_auth.service import McpOAuthService, digest

    code = authorization_code(oauth)
    service = oauth.native_app.state.context.get_bean(McpOAuthService)

    async def retained_legacy_code():
        row = (await service.repository.find_all(code_hash=digest(code)))[0]
        row.grant_json = {"tenant_id": "north", "workspace_ids": [oauth.workspace_id]}
        await service.repository.save(row)

    oauth.portal.call(retained_legacy_code)
    assert exchange(oauth, code).status_code == 400
    assert oauth.get("/api/v1/authorized-applications", headers=bearer()).json()["items"] == []


def test_browser_projection_uses_the_user_session_and_csrf_for_disconnect(oauth):
    from urllib.parse import unquote

    connected(oauth)
    response = oauth.get("/bff/api/v1/authorized-applications")
    assert response.status_code == 200
    identifier = response.json()["items"][0]["id"]
    assert oauth.delete("/bff/api/v1/authorized-applications/" + identifier).status_code == 403
    assert (
        oauth.delete(
            "/bff/api/v1/authorized-applications/" + identifier,
            headers={"X-XSRF-TOKEN": unquote(oauth.cookies.get("XSRF-TOKEN"))},
        ).status_code
        == 204
    )
