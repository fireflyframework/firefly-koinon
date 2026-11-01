# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from datetime import UTC, datetime

import httpx

from koinon_sdk import ActivitySummary, ActivityWindow, KoinonClient, ObservedCost, ObservedCount


def test_unknown_measurements_and_exact_cost_survive_the_sdk_wire_contract():
    unknown = ObservedCount.model_validate({"value": None, "status": "unavailable"})
    assert unknown.value is None
    exact = ObservedCost.model_validate(
        {"amount": "0.100000000000000001", "currency": "USD", "status": "observed", "source": "provider"}
    )
    assert exact.model_dump(mode="json")["amount"] == "0.100000000000000001"


async def test_summary_helpers_preserve_window_tenant_and_refresh_credentials_per_request():
    requests = []
    tokens = iter(("first-credential", "second-credential"))
    window = ActivityWindow(
        start_at=datetime(2026, 10, 1, tzinfo=UTC),
        end_at=datetime(2026, 11, 1, tzinfo=UTC),
        time_zone="Europe/Madrid",
    )
    unknown = {"value": None, "status": "unavailable"}
    counts = dict(created=unknown, updated=unknown, consulted=unknown)
    payload = dict(
        tenant_id="north/office",
        audience="personal",
        window=window.model_dump(mode="json"),
        coverage=dict(observed_since=None, complete_window=False, missing_observations=None),
        knowledge=counts,
        mcp={
            key: unknown
            for key in (
                "requests",
                "tool_calls",
                "succeeded",
                "failed",
                "rejected",
                "average_duration_ms",
                "p95_duration_ms",
            )
        },
        models=dict(
            input_tokens=unknown,
            output_tokens=unknown,
            embedding_tokens=unknown,
            cost=dict(status="unavailable"),
        ),
    )

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=payload)

    async with KoinonClient(
        "https://brain.test/api/v1",
        token_provider=lambda: next(tokens),
        transport=httpx.MockTransport(handle),
    ) as client:
        personal = await client.personal_activity("north/office", window)
        admin = await client.administrative_activity("north/office", window)
    assert isinstance(personal, ActivitySummary) and admin.coverage.missing_observations is None
    assert personal.models.cost.amount is None and personal.mcp.requests.value is None
    assert [request.headers["authorization"] for request in requests] == [
        "Bearer first-credential",
        "Bearer second-credential",
    ]
    assert requests[0].url.raw_path == b"/api/v1/tenants/north%2Foffice/activity/personal"
    assert requests[1].url.raw_path.endswith(b"/activity/administration")
    assert all(json.loads(request.content) == window.model_dump(mode="json") for request in requests)
