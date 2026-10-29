# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx

from koinon_sdk import KoinonClient


async def test_typed_organization_default_preserves_explicit_clear_and_scope_filters():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            json=dict(
                tenant_id="north/one",
                default_agent_id=None,
                revision=2,
                configured=False,
                can_run=False,
                status="unconfigured",
            ),
        )

    async with KoinonClient(
        "https://knowledge.example/api/v1",
        token_provider=lambda: "fixture",
        transport=httpx.MockTransport(handle),
    ) as client:
        current = await client.organization_chat_settings("north/one", workspace_id="w", project_id="p")
        assert current.status == "unconfigured"
        from koinon_sdk import OrganizationChatSettingsInput

        await client.update_organization_chat_settings(
            "north/one", OrganizationChatSettingsInput(default_agent_id=None, expected_revision=1)
        )
    assert calls[0].url.raw_path.startswith(b"/api/v1/tenants/north%2Fone/chat/settings?")
    assert dict(calls[0].url.params) == {"workspace_id": "w", "project_id": "p"}
    assert json.loads(calls[1].content) == {"default_agent_id": None, "expected_revision": 1}
