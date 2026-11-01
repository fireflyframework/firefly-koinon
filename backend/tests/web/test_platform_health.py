# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from conftest import ISSUER, bearer
from pyfly.security.context import SecurityContext
from pyfly.session.ports.outbound import SessionStore

PATHS = ("/platform/health", "/platform/system-information")


def test_platform_reports_are_admin_only_and_do_not_dump_deployment_configuration(client):
    for suffix in PATHS:
        path = "/api/v1/tenants/north" + suffix
        response = client.get(path, headers=bearer())
        assert response.status_code == 200, response.text
        assert response.json()["tenant_id"] == "north"
        assert "localhost" not in response.text and "site-packages" not in response.text
        assert "database_url" not in response.text.lower() and "secret_ciphertext" not in response.text
        assert client.get(path, headers=bearer("viewer")).status_code == 403
        assert client.get("/api/v1/tenants/south" + suffix, headers=bearer()).status_code == 403
        assert client.get(path).status_code == 401


def test_browser_projection_uses_real_session_with_no_bearer_fallback(client):
    store = client.native_app.state.context.get_bean(SessionStore)
    client.portal.call(
        store.save,
        "platform-browser",
        {"SECURITY_CONTEXT": SecurityContext(user_id="admin", attributes={"iss": ISSUER, "sub": "admin"})},
        1800,
    )
    client.cookies.set("PYFLY_SESSION", "platform-browser", domain="testserver.local", path="/")
    for suffix in PATHS:
        path = "/bff/api/v1/tenants/north" + suffix
        response = client.get(path)
        assert response.status_code == 200, response.text
        assert client.get(path, headers=bearer()).status_code == 400
        assert client.get("/api/v1/tenants/north" + suffix).status_code == 401


def test_platform_pat_requires_explicit_audit_scope_and_no_workspace_bound(client):
    base = {
        "name": "Platform",
        "tenant_id": "north",
        "scopes": ["catalog:read", "audit:read"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    for changes, expected in (
        ({}, 200),
        ({"scopes": ["catalog:read"]}, 403),
        ({"workspace_ids": [client.workspace_id]}, 403),
    ):
        created = client.post("/api/v1/tokens", headers=bearer(), json={**base, **changes})
        if "workspace_ids" in changes:
            assert created.status_code == 400
            assert created.json()["code"] == "INVALID_TOKEN_SCOPE"
            continue
        assert created.status_code == 201, created.text
        headers = {"Authorization": "Bearer " + created.json()["token"]}
        response = client.get("/api/v1/tenants/north/platform/system-information", headers=headers)
        assert response.status_code == expected, response.text
