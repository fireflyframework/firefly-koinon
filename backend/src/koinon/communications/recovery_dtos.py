# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit manual welcome recovery never asserts that an earlier delivery was absent."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from koinon.communications.dtos import DeliveryStatus


class WelcomeRecoveryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_generation: int = Field(strict=True, ge=0)
    contact_id: str = Field(min_length=1, max_length=64)
    expected_contact_revision: int = Field(strict=True, ge=1)
    reason: Literal["recipient_reported_not_received"]
    acknowledge_possible_duplicate: Literal[True]


class WelcomeRecoveryAcknowledgement(BaseModel):
    original_delivery_id: str
    delivery_id: str
    status: DeliveryStatus
    possible_original_late_arrival: Literal[True] = True


class DeliveryOperationObservation(BaseModel):
    id: str
    delivery_id: str
    source: Literal["operation_lookup"] = "operation_lookup"
    operation_state: Literal["checking", "pending", "accepted", "rejected", "unknown", "unavailable"]
    recipient_state: Literal["not_observed"] = "not_observed"
    checked_at: AwareDatetime | None = None
    reason_code: str | None = None


class DeliveryInspectionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    expected_generation: int = Field(strict=True, ge=0)


class DeliveryRecoveryOptions(BaseModel):
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


class DeliveryObservationPage(BaseModel):
    items: list[DeliveryOperationObservation]
    has_more: bool
