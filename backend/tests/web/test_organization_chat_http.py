# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from conftest import bearer


def test_settings_http_authorization_revision_validation_and_no_conversation_override(client):
    path = "/api/v1/tenants/north/chat/settings"
    assert client.get(path).status_code == 401
    first = client.get(path, headers=bearer("viewer"))
    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 0 and first.json()["default_agent_id"] is None
    assert (
        client.put(
            path, headers=bearer("viewer"), json={"default_agent_id": None, "expected_revision": 0}
        ).status_code
        == 403
    )
    saved = client.put(path, headers=bearer(), json={"default_agent_id": None, "expected_revision": 0})
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1
    assert (
        client.put(
            path, headers=bearer(), json={"default_agent_id": None, "expected_revision": 0}
        ).status_code
        == 409
    )
    assert client.put(
        path, headers=bearer(), json={"default_agent_id": None, "expected_revision": 1, "thread_id": "hidden"}
    ).status_code in {400, 422}
    assert client.put(
        path, headers=bearer(), json={"default_agent_id": None, "expected_revision": True}
    ).status_code in {400, 422}
    assert client.get(path, headers=bearer("outsider")).status_code == 403
    assert client.get(path + "?workspace_id=missing", headers=bearer()).status_code == 403


def test_workspace_pat_reads_only_with_explicit_bound_context_and_cannot_write_global_default(client):
    issued = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Bound chat",
            "tenant_id": "north",
            "workspace_ids": [client.workspace_id],
            "scopes": ["chat:use", "catalog:read"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert issued.status_code == 201, issued.text
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    path = "/api/v1/tenants/north/chat/settings"
    assert client.get(path, headers=headers).status_code == 403
    allowed = client.get(path + "?workspace_id=" + client.workspace_id, headers=headers)
    assert allowed.status_code == 200, allowed.text
    assert (
        client.put(path, headers=headers, json={"default_agent_id": None, "expected_revision": 0}).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/tenants/south/chat/settings?workspace_id=" + client.workspace_id, headers=headers
        ).status_code
        == 403
    )
