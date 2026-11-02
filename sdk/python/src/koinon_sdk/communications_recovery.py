# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/communications/recovery_dtos.py
SHA256: 8fcb9ec2fbd1932225a165d038bf2f4b2749e4c3554fdf7f2e644ef15cb46b1c

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.communications import DeliveryStatus


class WelcomeRecoveryInput(InputModel):
    expected_generation: int = Field(strict=True, ge=0)
    contact_id: str = Field(min_length=1, max_length=64)
    expected_contact_revision: int = Field(strict=True, ge=1)
    reason: Literal["recipient_reported_not_received"]
    acknowledge_possible_duplicate: Literal[True]


class WelcomeRecoveryAcknowledgement(ResponseModel):
    original_delivery_id: str
    delivery_id: str
    status: DeliveryStatus
    possible_original_late_arrival: Literal[True] = True


class DeliveryOperationObservation(ResponseModel):
    id: str
    delivery_id: str
    source: Literal["operation_lookup"] = "operation_lookup"
    operation_state: Literal["checking", "pending", "accepted", "rejected", "unknown", "unavailable"]
    recipient_state: Literal["not_observed"] = "not_observed"
    checked_at: AwareDatetime | None = None
    reason_code: str | None = None


class DeliveryInspectionInput(InputModel):
    expected_generation: int = Field(strict=True, ge=0)


class DeliveryRecoveryOptions(ResponseModel):
    delivery_id: str
    generation: int
    submission_status: DeliveryStatus
    attempt_count: int
    can_inspect: bool
    inspection_reason: str | None = None
    provider_binding_state: Literal["verified", "operator_verification_required", "unavailable"]
    can_recover_welcome: bool
    recovery_reason: str | None = None
    contact_id: str | None = None
    contact_revision: int | None = None
    possible_original_late_arrival: Literal[True] = True


class DeliveryObservationPage(ResponseModel):
    items: list[DeliveryOperationObservation]
    has_more: bool
