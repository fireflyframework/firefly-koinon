# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Actual native production resolvers persist observations before API and MCP reports."""

from datetime import UTC, datetime, timedelta

from http_fixtures import bearer
from http_fixtures import client as client
from test_mcp_http import call, create_pat


def test_actual_mcp_observations_are_visible_through_typed_api_and_mcp_without_test_recorders(client):
    issued = create_pat(client, scopes=["catalog:read", "activity:read"])
    token = issued["token"]
    assert call(client, token, "koinon_context").status_code == 200
    window = {
        "start_at": (datetime.now(UTC) - timedelta(minutes=5)).isoformat(),
        "end_at": (datetime.now(UTC) + timedelta(seconds=1)).isoformat(),
        "time_zone": "UTC",
    }
    report = client.post(
        "/api/v1/tenants/north/activity/personal", json=window, headers={"Authorization": "Bearer " + token}
    )
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["mcp"]["requests"]["value"] == 1
    assert data["mcp"]["tool_calls"]["value"] == 1
    assert data["mcp"]["tool_calls"]["status"] == "partial"
    assert data["models"]["cost"]["amount"] is None
    assert token not in report.text
    answer = call(client, token, "koinon_activity_summary", {"tenant_id": "north", "window": window})
    assert answer.status_code == 200 and answer.json()["result"].get("isError") is not True, answer.text
    assert answer.json()["result"]["structuredContent"]["mcp"]["tool_calls"]["value"] == 1
    denied = client.post(
        "/api/v1/tenants/north/activity/administration",
        json=window,
        headers={"Authorization": "Bearer " + token},
    )
    assert denied.status_code == 403
    assert client.delete("/api/v1/tokens/" + issued["id"], headers=bearer()).status_code == 204
    revoked = client.post(
        "/api/v1/tenants/north/activity/personal", json=window, headers={"Authorization": "Bearer " + token}
    )
    assert revoked.status_code == 401
