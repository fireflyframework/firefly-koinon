# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import httpx

from koinon_sdk import KoinonClient


async def test_passive_helpers_encode_tenant_refresh_bearer_and_preserve_unknown():
    requests = []
    credentials = iter(("first", "second"))
    stamp = datetime(2026, 11, 1, tzinfo=UTC).isoformat()

    def handle(request):
        requests.append(request)
        if request.url.path.endswith("/health"):
            payload = {
                "tenant_id": "north/office",
                "checked_at": stamp,
                "summary": {"passed": 0, "failed": 0, "unknown": 0, "disabled": 0},
                "components": [],
            }
        else:
            payload = {
                "tenant_id": "north/office",
                "checked_at": stamp,
                "product": "koinon",
                "components": [],
                "serving_role": "unknown",
                "capabilities": {
                    "knowledge_enabled": False,
                    "mcp_enabled": False,
                    "communications_enabled": False,
                    "scheduled_consumers_enabled": False,
                },
                "limits": [],
                "build_revision": None,
                "artifacts": [],
            }
        return httpx.Response(200, json=payload)

    async with KoinonClient(
        "https://api.test/api/v1",
        token_provider=lambda: next(credentials),
        transport=httpx.MockTransport(handle),
    ) as client:
        health = await client.platform_health("north/office")
        info = await client.system_information("north/office")
    assert health.summary.unknown == 0 and info.build_revision is None
    assert [request.headers["authorization"] for request in requests] == ["Bearer first", "Bearer second"]
    assert all(request.method == "GET" and not request.content for request in requests)
    assert requests[0].url.raw_path == b"/api/v1/tenants/north%2Foffice/platform/health"
    assert requests[1].url.raw_path.endswith(b"/platform/system-information")
