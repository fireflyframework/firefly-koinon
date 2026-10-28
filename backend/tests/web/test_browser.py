# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import ISSUER
from pyfly.security.context import SecurityContext
from pyfly.session.ports.outbound import SessionStore


def test_bff_projection_uses_session_csrf_and_no_bearer_fallback(client):
    context = client.native_app.state.context
    store = context.get_bean(SessionStore)
    session = {
        "SECURITY_CONTEXT": SecurityContext(user_id="admin", attributes={"iss": ISSUER, "sub": "admin"})
    }
    client.portal.call(store.save, "browser-session", session, 1800)
    client.cookies.set("PYFLY_SESSION", "browser-session", domain="testserver.local", path="/")
    assert client.get("/bff/api/v1/context").status_code == 200
    body = {"kind": "project", "name": "Browser project", "parent_id": client.workspace_id}
    url = "/bff/api/v1/tenants/north/catalog"
    assert client.post(url, json=body).status_code == 403
    response = client.post(url, json=body, headers={"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN")})
    assert response.status_code == 201, response.text
    assert client.get("/api/v1/context").status_code == 401
    assert client.get("/bff/api/v1/context", headers={"Authorization": "Bearer invalid"}).status_code == 400
