# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from koinon.activity.dtos import ActivityWindow, ObservedCost, ObservedCount
from koinon.activity.observations import McpObservation


def test_measurement_never_invents_zero_for_unavailable_observations():
    assert ObservedCount(value=0, status="observed").value == 0
    assert ObservedCount(status="unavailable").value is None
    with pytest.raises(ValidationError):
        ObservedCount(value=0, status="unavailable")
    with pytest.raises(ValidationError):
        ObservedCount(status="observed")


def test_observed_cost_requires_its_value_and_currency():
    with pytest.raises(ValidationError):
        ObservedCost(status="observed")
    with pytest.raises(ValidationError):
        ObservedCost(status="unavailable", amount="1.23", currency="EUR")
    assert ObservedCost(status="observed", amount="0", currency="USD", source="provider").amount == 0


def test_windows_are_aware_positive_bounded_and_use_a_real_time_zone():
    start, end = datetime(2026, 10, 1, tzinfo=UTC), datetime(2026, 11, 1, tzinfo=UTC)
    assert ActivityWindow(start_at=start, end_at=end, time_zone="Europe/Madrid").end_at == end
    for values in (
        {"start_at": start.replace(tzinfo=None)},
        {"end_at": start},
        {"time_zone": "Unknown/Zone"},
        {"end_at": datetime(2028, 1, 1, tzinfo=UTC)},
    ):
        with pytest.raises(ValidationError):
            ActivityWindow(**({"start_at": start, "end_at": end, "time_zone": "UTC"} | values))


def test_request_and_tool_observations_cannot_masquerade_as_each_other():
    values = dict(
        observation_id=uuid4(),
        tenant_id="north",
        subject="issuer|person",
        outcome="succeeded",
        duration_ms=12,
    )
    assert McpObservation(**values, kind="request", operation="POST").kind == "request"
    assert McpObservation(**values, kind="tool", operation="koinon_search").kind == "tool"
    with pytest.raises(ValidationError):
        McpObservation(**values, kind="request", operation="koinon_search")
    with pytest.raises(ValidationError):
        McpObservation(**values, kind="tool", operation="https://private.example/secret")
