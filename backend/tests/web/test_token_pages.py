# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from conftest import bearer


def test_token_pages_filter_status_and_owner_before_counting(client):
    def mint(name, actor="admin"):
        response = client.post(
            "/api/v1/tokens",
            headers=bearer(actor),
            json={
                "name": name,
                "tenant_id": "north",
                "scopes": ["catalog:read"],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    first, second, revoked = mint("Alpha A"), mint("Alpha B"), mint("Alpha C")
    mint("Alpha foreign owner", "viewer")
    assert client.delete("/api/v1/tokens/" + revoked["id"], headers=bearer()).status_code == 204
    query = "?q=Alpha&status=active&page_size=1&sort=name&order=asc"
    page = client.get("/api/v1/tokens" + query, headers=bearer()).json()
    assert page["total"] == 2 and page["pages"] == 2 and page["page_size"] == 1
    assert [row["id"] for row in page["items"]] == [first["id"]]
    next_page = client.get("/api/v1/tokens" + query + "&page=2", headers=bearer()).json()
    assert [row["id"] for row in next_page["items"]] == [second["id"]]
    for secret in (first["token"], second["token"], revoked["token"]):
        assert secret not in str(page)
    history = client.get("/api/v1/tokens?status=revoked", headers=bearer()).json()
    assert history["total"] == 1 and history["items"][0]["id"] == revoked["id"]
    assert client.get("/api/v1/tokens?page_size=101", headers=bearer()).status_code == 400
    assert client.get("/api/v1/tokens?status=unknown", headers=bearer()).status_code == 400
