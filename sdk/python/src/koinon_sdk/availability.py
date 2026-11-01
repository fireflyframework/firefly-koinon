# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/availability/dtos.py
SHA256: 0db6cc4b12d8d26a8d12d529fdfc7cd0b28fb4ebbe2a748085e3287fd5005011

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel

AvailabilityState = Literal["ready", "pending", "unavailable", "unknown", "not_applicable"]
ProcessingPhase = Literal[
    "unknown",
    "queued",
    "processing",
    "indexing",
    "complete",
    "failed",
    "cancelled",
    "reconciliation_required",
]


class AvailabilityRequest(InputModel):
    asset_ids: list[Annotated[str, Field(strict=True, min_length=1, max_length=64)]] = Field(
        min_length=1, max_length=100
    )
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)


class AvailabilityCapability(ResponseModel):
    state: AvailabilityState = "unknown"
    reason: str = "NOT_OBSERVED"


class AvailabilityRevision(ResponseModel):
    source_version_id: str | None = None
    extraction_id: str | None = None
    snapshot_id: str | None = None
    active_index_id: str | None = None


class AvailabilityAttempt(ResponseModel):
    id: str
    operation: str
    state: ProcessingPhase


class AssetAvailability(ResponseModel):
    phase: ProcessingPhase = "unknown"
    read: AvailabilityCapability = Field(default_factory=AvailabilityCapability)
    search: AvailabilityCapability = Field(default_factory=AvailabilityCapability)
    query: AvailabilityCapability = Field(default_factory=AvailabilityCapability)
    revision: AvailabilityRevision = Field(default_factory=AvailabilityRevision)
    latest_attempt: AvailabilityAttempt | None = None


class AvailabilityResponse(ResponseModel):
    observed_at: datetime
    items: dict[str, AssetAvailability]


class ProcessingRequest(InputModel):
    page: int = Field(default=1, ge=1, le=100000, strict=True)
    page_size: int = Field(default=25, ge=1, le=50, strict=True)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)


class ProcessingActivity(ResponseModel):
    id: str
    resource_id: str
    operation: str
    state: ProcessingPhase
    updated_at: datetime
    availability: AssetAvailability


class ProcessingResponse(ResponseModel):
    observed_at: datetime
    items: list[ProcessingActivity]
    next_page: int | None = None
