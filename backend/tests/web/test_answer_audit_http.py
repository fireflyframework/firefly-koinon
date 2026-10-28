# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from conftest import bearer
from test_chat_sse import seed


def test_owner_audit_uses_chat_scope_preserves_unknown_and_rechecks_original_pat(client):
    run_id = client.portal.call(seed, client.native_app.state.context)
    url = f"/api/v1/tenants/north/chat/runs/{run_id}/audit"
    response = client.get(url, headers=bearer())
    assert response.status_code == 200, response.text
    assert response.json()["provenance_status"] == "not_recorded"
    assert response.json()["source_provenance_complete"] is None
    assert response.json()["generations"] == []
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get(url, headers=bearer("viewer")).status_code == 403
    assert client.get(url.replace("north", "south"), headers=bearer("outsider")).status_code == 403
    created = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Owner audit",
            "tenant_id": "north",
            "scopes": ["chat:use"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert created.status_code == 201, created.text
    token = created.json()
    assert client.get(url, headers={"Authorization": "Bearer " + token["token"]}).status_code == 200

    async def origin():
        from koinon.assistants.repositories import ChatRunRepository

        repository = client.native_app.state.context.get_bean(ChatRunRepository)
        run = await repository.find_by_id(run_id)
        run.access_token_id = token["id"]
        await repository.save(run)

    client.portal.call(origin)
    assert client.get(url, headers=bearer()).status_code == 200
    assert client.delete("/api/v1/tokens/" + token["id"], headers=bearer()).status_code == 204
    assert client.get(url, headers=bearer()).status_code == 403
