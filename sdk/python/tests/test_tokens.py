# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from datetime import UTC, datetime, timedelta

import httpx

from koinon_sdk import KoinonClient, TokenInput


async def test_personal_token_management_is_explicit_and_new_secret_is_not_logged():
    response = {
        "id": "token-id",
        "name": "Forge",
        "tenant_id": "north",
        "prefix": "koinon_pat_public",
        "scopes": ["profile:read"],
        "expires_at": "2026-11-26T00:00:00Z",
        "created_at": "2026-10-26T00:00:00Z",
    }
    calls = []

    def handle(request):
        calls.append(request)
        if request.method == "POST":
            assert json.loads(request.content)["expires_at"].endswith("Z")
            return httpx.Response(201, json={**response, "token": "owned-private-once"})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(200, json={"items": [response]})

    async with KoinonClient(
        "https://api.test/api/v1",
        token_provider=lambda: "interactive-identity",
        transport=httpx.MockTransport(handle),
    ) as client:
        created = await client.create_token(
            TokenInput(
                name="Forge",
                tenant_id="north",
                scopes=["profile:read"],
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        assert "owned-private-once" not in repr(created)
        assert created.token.get_secret_value() == "owned-private-once"
        assert (await client.tokens()).items[0].id == "token-id"
        await client.revoke_token("token-id")
    assert [request.method for request in calls] == ["POST", "GET", "DELETE"]


async def test_scope_options_come_from_authorized_server_descriptors():
    def handle(request):
        assert request.url.path.endswith("/tokens/scopes")
        assert request.url.params["workspace_id"] == "workspace-a"
        return httpx.Response(
            200,
            json={
                "items": [{"id": "profile:read", "name": "Read profile", "dependencies": []}],
                "max_lifetime_days": 365,
                "max_active_per_user": 100,
            },
        )

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "interactive", transport=httpx.MockTransport(handle)
    ) as client:
        options = await client.token_scopes("north", workspace_id="workspace-a")
        assert options.items[0].id == "profile:read"
