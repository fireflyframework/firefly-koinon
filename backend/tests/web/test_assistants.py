# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import bearer


def test_assistant_routes_use_native_auth_and_persist_owner_only_threads(client):
    prefix = "/api/v1/tenants/north"
    assert client.get(prefix + "/agents").status_code == 401
    assert client.get(prefix + "/configuration", headers=bearer("viewer")).status_code == 403
    thread = client.post(prefix + "/chat/threads", headers=bearer("viewer"), json={"title": "Planning"})
    assert thread.status_code == 201, thread.text
    thread_id = thread.json()["id"]
    response = client.get(prefix + "/chat/threads", headers=bearer("viewer"))
    assert response.json()["items"][0]["id"] == thread_id
    assert (
        client.get(prefix + f"/chat/threads/{thread_id}/messages", headers=bearer("admin")).status_code == 403
    )
    assert client.get(prefix + f"/chat/threads/{thread_id}/messages", headers=bearer("viewer")).json() == {
        "items": [],
        "next_cursor": None,
    }
    assert (
        client.post(
            prefix + "/providers", headers=bearer("viewer"), json={"name": "Denied", "kind": "ollama"}
        ).status_code
        == 403
    )


def test_agent_inputs_reject_unknown_fields_and_foreign_organization(client):
    prefix = "/api/v1/tenants/north"
    assert (
        client.post(
            prefix + "/agents", headers=bearer(), json={"name": "Guide", "trust_browser": True}
        ).status_code
        == 422
    )
    assert client.get("/api/v1/tenants/south/agents", headers=bearer()).status_code == 403
