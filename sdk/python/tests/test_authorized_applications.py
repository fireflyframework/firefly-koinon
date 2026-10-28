# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx

from koinon_sdk import AuthorizedApplication, KoinonClient


async def test_authorized_connections_are_typed_paginated_and_revoked_without_a_secret():
    connection = {
        "id": "app/one",
        "client_id": "desktop-client",
        "name": "Desktop client",
        "resource": "https://knowledge.example/mcp",
        "tenant_id": "north",
        "tenant_name": "North",
        "workspace_id": "research",
        "workspace_name": "Research",
        "scopes": ["catalog:read"],
        "status": "active",
        "connected_at": "2026-10-28T00:00:00Z",
        "expires_at": "2026-10-29T00:00:00Z",
        "last_used_at": None,
        "revoked_at": None,
    }
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        if b"app%2Fone" in request.url.raw_path:
            return httpx.Response(200, json=connection)
        assert dict(request.url.params) == {"page": "2", "page_size": "10", "status": "active"}
        return httpx.Response(
            200, json={"items": [connection], "total": 11, "page": 2, "page_size": 10, "pages": 2}
        )

    async with KoinonClient(
        "https://knowledge.example/api/v1",
        token_provider=lambda: "interactive-user",
        transport=httpx.MockTransport(handle),
    ) as client:
        page = await client.authorized_applications(page=2, page_size=10, status="active")
        assert page.page == 2 and isinstance(page.items[0], AuthorizedApplication)
        assert page.items[0].connected_at.tzinfo is not None
        assert (await client.authorized_application("app/one")).workspace_name == "Research"
        await client.revoke_authorized_application("app/one")
    assert [request.method for request in calls] == ["GET", "GET", "DELETE"]
    assert calls[-1].url.raw_path.endswith(b"/authorized-applications/app%2Fone")
    assert calls[-1].content == b""
