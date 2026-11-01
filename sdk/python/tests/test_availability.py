# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest

from koinon_sdk import AvailabilityRequest, KoinonClient, ProcessingRequest


async def test_availability_keeps_serving_revision_separate_from_failed_attempt_and_fresh_auth():
    requests = []
    tokens = iter(("fresh-one", "fresh-two"))
    observed = {
        "phase": "failed",
        "read": {"state": "ready", "reason": "CURRENT_TEXT_RECORDED"},
        "search": {"state": "pending", "reason": "ACTIVE_INDEX_INCOMPLETE"},
        "revision": {"source_version_id": "old-serving", "extraction_id": "old-extraction"},
        "latest_attempt": {"id": "new-failed", "operation": "document.replace", "state": "failed"},
    }

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "observed_at": "2026-11-01T00:00:00Z",
                "items": {"asset": observed} if request.url.path.endswith("availability") else [],
                "next_page": None,
            },
        )

    async with KoinonClient(
        "https://brain.test/api/v1",
        token_provider=lambda: next(tokens),
        transport=httpx.MockTransport(handle),
    ) as client:
        response = await client.knowledge_availability(
            "north/office", AvailabilityRequest(asset_ids=["asset"], workspace_id="space")
        )
        history = await client.knowledge_processing("north/office", ProcessingRequest(page_size=1))
    asset = response.items["asset"]
    assert asset.read.state == "ready" and asset.latest_attempt.state == "failed"
    assert asset.revision.source_version_id == "old-serving" and asset.search.state == "pending"
    assert history.next_page is None
    assert [r.headers["authorization"] for r in requests] == ["Bearer fresh-one", "Bearer fresh-two"]
    assert requests[0].url.raw_path == b"/api/v1/tenants/north%2Foffice/catalog/availability"
    assert json.loads(requests[0].content) == {"asset_ids": ["asset"], "workspace_id": "space"}
    assert requests[1].url.raw_path.endswith(b"/knowledge-processing")


def test_availability_wire_inputs_remain_bounded():
    from pydantic import ValidationError

    for ids in ([], ["x"] * 101):
        with pytest.raises(ValidationError):
            AvailabilityRequest(asset_ids=ids)
    with pytest.raises(ValidationError):
        ProcessingRequest(page_size=51)
