# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Availability observations are separate from immutable operation receipts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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


class AvailabilityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_ids: list[Annotated[str, Field(strict=True, min_length=1, max_length=64)]] = Field(
        min_length=1, max_length=100
    )

    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("asset_ids")
    @classmethod
    def unique(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("Select each asset once")
        return value


class AvailabilityCapability(BaseModel):
    model_config = ConfigDict(frozen=True)
    state: AvailabilityState = "unknown"
    reason: str = "NOT_OBSERVED"


class AvailabilityRevision(BaseModel):
    model_config = ConfigDict(frozen=True)
    source_version_id: str | None = None
    extraction_id: str | None = None
    snapshot_id: str | None = None
    active_index_id: str | None = None


class AvailabilityAttempt(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    operation: str
    state: ProcessingPhase


class AssetAvailability(BaseModel):
    model_config = ConfigDict(frozen=True)
    phase: ProcessingPhase = "unknown"
    read: AvailabilityCapability = Field(default_factory=AvailabilityCapability)
    search: AvailabilityCapability = Field(default_factory=AvailabilityCapability)
    query: AvailabilityCapability = Field(default_factory=AvailabilityCapability)
    revision: AvailabilityRevision = Field(default_factory=AvailabilityRevision)
    latest_attempt: AvailabilityAttempt | None = None


class AvailabilityResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    observed_at: datetime
    items: dict[str, AssetAvailability]


class ProcessingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: int = Field(default=1, ge=1, le=100000, strict=True)
    page_size: int = Field(default=25, ge=1, le=50, strict=True)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)


class ProcessingActivity(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    resource_id: str
    operation: str
    state: ProcessingPhase
    updated_at: datetime
    availability: AssetAvailability


class ProcessingResponse(BaseModel):
    model_config = ConfigDict(frozen=True)
    observed_at: datetime
    items: list[ProcessingActivity]
    next_page: int | None = None
