# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import KoinonClient
from koinon_sdk.communications_recovery import DeliveryInspectionInput, WelcomeRecoveryInput


@pytest.mark.asyncio
async def test_typed_delivery_inspection_and_welcome_recovery_preserve_exact_keys_and_never_replay():
    calls = []
    observation = dict(
        id="observation",
        delivery_id="original",
        source="operation_lookup",
        operation_state="accepted",
        recipient_state="not_observed",
        checked_at=None,
        reason_code=None,
    )
    options = dict(
        delivery_id="original",
        generation=4,
        submission_status="unknown",
        attempt_count=1,
        can_inspect=True,
        inspection_reason=None,
        provider_binding_state="verified",
        can_recover_welcome=True,
        recovery_reason=None,
        contact_id="approved-contact",
        contact_revision=3,
        possible_original_late_arrival=True,
    )

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/recovery"):
            value = options
        elif request.url.path.endswith("/welcome-recovery"):
            value = dict(
                original_delivery_id="original",
                delivery_id="new-linked",
                status="queued",
                possible_original_late_arrival=True,
            )
        elif request.method == "GET":
            value = dict(items=[observation], has_more=False)
        else:
            value = observation
        return httpx.Response(200, json=value)

    async with KoinonClient(
        base_url="https://example.invalid/api/v1",
        token_provider=lambda: "scoped-admin",
        transport=httpx.MockTransport(handler),
    ) as client:
        current = await client.communication_delivery_recovery("north", "original")
        history = await client.communication_delivery_observations("north", "original")
        observed = await client.inspect_communication_delivery(
            "north",
            "original",
            DeliveryInspectionInput(expected_generation=current.generation),
            "inspection-key",
        )
        linked = await client.recover_welcome_delivery(
            "north",
            "original",
            WelcomeRecoveryInput(
                expected_generation=current.generation,
                contact_id=current.contact_id,
                expected_contact_revision=current.contact_revision,
                reason="recipient_reported_not_received",
                acknowledge_possible_duplicate=True,
            ),
            "welcome-key",
        )
    assert history.items[0].id == observed.id and observed.recipient_state == "not_observed"
    assert linked.original_delivery_id == "original" and linked.delivery_id == "new-linked"
    assert len(calls) == 4
    assert calls[2].headers["Idempotency-Key"] == "inspection-key"
    assert json.loads(calls[2].content) == {"expected_generation": 4}
    assert calls[3].headers["Idempotency-Key"] == "welcome-key"
    assert json.loads(calls[3].content) == dict(
        expected_generation=4,
        contact_id="approved-contact",
        expected_contact_revision=3,
        reason="recipient_reported_not_received",
        acknowledge_possible_duplicate=True,
    )


def test_welcome_recovery_requires_explicit_acknowledgment_and_a_typed_generation():
    body = dict(
        expected_generation=0,
        contact_id="approved",
        expected_contact_revision=1,
        reason="recipient_reported_not_received",
        acknowledge_possible_duplicate=True,
    )
    assert WelcomeRecoveryInput.model_validate(body).expected_generation == 0
    for changed in (
        {"acknowledge_possible_duplicate": False},
        {"expected_generation": True},
        {"recipient_email": "not-allowed@example.invalid"},
    ):
        with pytest.raises(ValidationError):
            WelcomeRecoveryInput.model_validate({**body, **changed})
