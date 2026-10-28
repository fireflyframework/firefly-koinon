# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx

from koinon_sdk import InvitationInput, KoinonClient


async def test_members_filters_and_invitation_token_are_typed_and_not_logged():
    seen = []
    member = {
        "id": "m",
        "tenant_id": "t",
        "subject": "issuer|user",
        "workspace_id": None,
        "role": "viewer",
        "active": True,
    }
    invitation = {
        "id": "i",
        "tenant_id": "t",
        "workspace_id": None,
        "role": "viewer",
        "label": "Join",
        "created_by": "issuer|admin",
        "created_at": "2026-10-27T00:00:00Z",
        "expires_at": "2026-10-28T00:00:00Z",
        "status": "pending",
    }
    secret = "unlogged-" + "x" * 50

    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/members"):
            return httpx.Response(
                200,
                json={
                    "items": [member],
                    "actors": {"issuer|user": {"subject": "issuer|user", "display_name": "Málaga"}},
                    "page": 2,
                    "page_size": 1,
                    "pages": 3,
                    "total": 3,
                },
            )
        if request.url.path.endswith("/inspect"):
            return httpx.Response(
                200,
                json={
                    "id": "i",
                    "tenant_id": "t",
                    "tenant_name": "Team",
                    "workspace_id": None,
                    "workspace_name": None,
                    "role": "viewer",
                    "expires_at": invitation["expires_at"],
                },
            )
        if request.url.path.endswith("/redeem"):
            return httpx.Response(201, json=member)
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.method == "GET":
            return httpx.Response(
                200, json={"items": [invitation], "total": 1, "page": 1, "page_size": 2, "pages": 1}
            )
        return httpx.Response(201, json={"invitation": invitation, "token": secret})

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        page = await client.members("t", q="Málaga", role="viewer", scope="tenant", page=2, page_size=1)
        assert page.total == 3 and page.actors["issuer|user"].display_name == "Málaga"
        created = await client.create_invitation("t", InvitationInput(role="viewer", workspace_id=None))
        assert created.token.get_secret_value() == secret and secret not in repr(created)
        preview = await client.inspect_invitation(created.token.get_secret_value())
        assert preview.tenant_name == "Team"
        assert (await client.redeem_invitation(secret)).subject == "issuer|user"
        assert (await client.invitations("t", status="accepted", page_size=2)).items[0].id == "i"
        await client.revoke_invitation("t", "i/one")
    assert dict(seen[0].url.params) == {
        "q": "Málaga",
        "role": "viewer",
        "scope": "tenant",
        "page": "2",
        "page_size": "1",
    }
    assert json.loads(seen[1].content) == {"role": "viewer", "workspace_id": None}
    assert json.loads(seen[2].content) == {"token": secret}
    assert seen[-1].url.raw_path.endswith(b"/invitations/i%2Fone")


async def test_audit_filters_preserve_explicit_calendar_zone_and_workspace_capabilities():
    seen = []

    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/context"):
            return httpx.Response(
                200, json={"subject": "issuer|user", "workspace_permissions": {"workspace": ["catalog:read"]}}
            )
        return httpx.Response(
            200, json={"items": [], "total": 0, "page": 2, "page_size": 3, "pages": 0, "actors": {}}
        )

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        result = await client.audit(
            "tenant/one",
            q="Málaga",
            action="catalog.updated",
            subject="issuer|user",
            from_date="2026-03-08",
            through_date="2026-03-08",
            time_zone="America/Los_Angeles",
            page=2,
            page_size=3,
            sort="action",
            order="asc",
        )
        assert result.total == 0
        assert (await client.context()).workspace_permissions == {"workspace": ["catalog:read"]}
    assert dict(seen[0].url.params) == {
        "q": "Málaga",
        "action": "catalog.updated",
        "subject": "issuer|user",
        "from_date": "2026-03-08",
        "through_date": "2026-03-08",
        "time_zone": "America/Los_Angeles",
        "page": "2",
        "page_size": "3",
        "sort": "action",
        "order": "asc",
    }
