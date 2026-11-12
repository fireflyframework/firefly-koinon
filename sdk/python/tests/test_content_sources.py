# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx

from koinon_sdk import KoinonClient


async def test_owner_source_helpers_preserve_pagination_revision_and_no_consent_shortcut():
    requests = []
    connection = dict(
        id="connection",
        provider="google_drive",
        status="disconnected",
        revision=3,
        account=None,
        synchronization_available=False,
    )

    def handle(request):
        requests.append(request)
        if request.url.path.endswith("/connections"):
            return httpx.Response(
                200, json={"items": [connection], "next_cursor": "next", "synchronization_available": False}
            )
        return httpx.Response(200, json=connection)

    async with KoinonClient(
        "https://brain.invalid/api/v1", token_provider=lambda: "inert", transport=httpx.MockTransport(handle)
    ) as client:
        page = await client.source_connections("north/office", cursor="previous", limit=2)
        assert page.next_cursor == "next" and page.items[0].id == "connection"
        from koinon_sdk.content_sources import SourceConnectionRevision

        result = await client.disconnect_source_connection(
            "north/office", "connection", SourceConnectionRevision(expected_revision=2)
        )
        assert result.status == "disconnected" and result.revision == 3
        assert not hasattr(client, "begin_source_authorization")
    assert requests[0].url.raw_path.startswith(b"/api/v1/tenants/north%2Foffice/content-sources/connections?")
    assert dict(requests[0].url.params) == {"cursor": "previous", "limit": "2"}
    assert requests[1].method == "POST" and json.loads(requests[1].content) == {"expected_revision": 2}
    assert len(requests) == 2
