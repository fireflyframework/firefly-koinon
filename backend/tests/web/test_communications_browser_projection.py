# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from conftest import ISSUER, bearer
from pyfly.security.context import SecurityContext
from pyfly.session.ports.outbound import SessionStore


def session(client, subject):
    store = client.native_app.state.context.get_bean(SessionStore)
    client.portal.call(
        store.save,
        "communications-browser",
        {"SECURITY_CONTEXT": SecurityContext(user_id=subject, attributes={"iss": ISSUER, "sub": subject})},
        1800,
    )
    client.cookies.set("PYFLY_SESSION", "communications-browser", domain="testserver.local", path="/")
    assert client.get("/bff/api/v1/context").status_code == 200
    return {"X-XSRF-TOKEN": client.cookies.get("XSRF-TOKEN")}


def test_browser_communications_settings_and_notifications_have_real_routes(client):
    session(client, "admin")
    for path in (
        "/tenants/north/communications/policy",
        "/tenants/north/communications/capabilities",
        "/notifications",
        "/notifications/unread-count",
        "/notifications/preferences",
    ):
        response = client.get("/bff/api/v1" + path)
        assert response.status_code == 200, (path, response.text)
    assert client.get("/api/v1/tenants/north/communications/policy").status_code == 401
    assert client.get("/bff/api/v1/tenants/north/communications/policy", headers=bearer()).status_code == 400


def test_browser_personal_activity_is_self_owned_and_preserves_csrf_and_admin_boundary(client):
    headers = session(client, "viewer")
    window = {
        "start_at": (datetime.now(UTC) - timedelta(days=1)).isoformat(),
        "end_at": datetime.now(UTC).isoformat(),
        "time_zone": "UTC",
    }
    base = "/bff/api/v1/tenants/north/activity/"
    assert client.post(base + "personal", json=window).status_code == 403
    response = client.post(base + "personal", json=window, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["audience"] == "personal" and response.json()["tenant_id"] == "north"
    assert client.post(base + "administration", json=window, headers=headers).status_code == 403
    assert client.get("/bff/api/v1/tenants/north/communications/policy").status_code == 403
    assert client.post(
        "/bff/api/v1/tenants/south/activity/personal", json=window, headers=headers
    ).status_code == 403
