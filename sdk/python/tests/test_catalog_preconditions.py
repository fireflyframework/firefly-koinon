# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from datetime import datetime

import httpx
import pytest

from koinon_sdk import CatalogPrecondition, KoinonClient


async def test_catalog_helpers_preserve_exact_microseconds_and_bodyless_compatibility():
    requests = []
    observed = datetime.fromisoformat("2026-11-01T15:01:02.123456+00:00")

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "item",
                "tenant_id": "north",
                "kind": "collection",
                "name": "Name",
                "status": "ready",
                "created_at": observed.isoformat(),
            },
        )

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "fixture", transport=httpx.MockTransport(handle)
    ) as client:
        await client.archive("north", "item")
        await client.archive("north", "item", expected_updated_at=observed)
        await client.restore("north", "item", expected_updated_at=observed)
        await client.update("north", "item", name="Updated", expected_updated_at=observed)
    assert not requests[0].url.query
    assert all(
        request.url.params["expected_updated_at"] == "2026-11-01T15:01:02.123456Z"
        for request in requests[1:3]
    )
    assert json.loads(requests[3].content)["expected_updated_at"] == "2026-11-01T15:01:02.123456Z"
    with pytest.raises(ValueError):
        CatalogPrecondition(expected_updated_at=datetime(2026, 11, 1))
