# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Wire values distinguish recorded measurements from missing observations."""

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ActivityValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ActivityWindow(ActivityValue):
    start_at: datetime
    end_at: datetime
    time_zone: str = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def bounded_window(self) -> Self:
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None:
            raise ValueError("Activity windows require timezone-aware boundaries")
        if not 0 < (self.end_at - self.start_at).total_seconds() <= 366 * 86400:
            raise ValueError("Activity windows must be positive and at most 366 days")
        try:
            ZoneInfo(self.time_zone)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Activity windows require an IANA time zone") from None
        return self


class ObservedCount(ActivityValue):
    value: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    status: Literal["observed", "partial", "unavailable"]
    reason: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if (self.status == "unavailable") != (self.value is None):
            raise ValueError("Unavailable measurements have no invented numeric value")
        return self


class ActivityCoverage(ActivityValue):
    observed_since: datetime | None
    complete_window: bool
    missing_observations: int | None = Field(default=None, strict=True, ge=0)
    reasons: list[str] = Field(default_factory=list, max_length=10)


class KnowledgeActivityCounts(ActivityValue):
    created: ObservedCount
    updated: ObservedCount
    consulted: ObservedCount


class ProjectActivity(ActivityValue):
    project_id: str = Field(min_length=1, max_length=64)
    workspace_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    knowledge: KnowledgeActivityCounts


class DailyActivity(ActivityValue):
    local_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    knowledge: KnowledgeActivityCounts
    mcp_tool_calls: ObservedCount


class McpActivityCounts(ActivityValue):
    requests: ObservedCount
    tool_calls: ObservedCount
    succeeded: ObservedCount
    failed: ObservedCount
    rejected: ObservedCount
    average_duration_ms: ObservedCount
    p95_duration_ms: ObservedCount
    tool_cancelled: ObservedCount = Field(default_factory=lambda: ObservedCount(status="unavailable"))
    request_succeeded: ObservedCount = Field(default_factory=lambda: ObservedCount(status="unavailable"))
    request_failed: ObservedCount = Field(default_factory=lambda: ObservedCount(status="unavailable"))
    request_rejected: ObservedCount = Field(default_factory=lambda: ObservedCount(status="unavailable"))
    request_cancelled: ObservedCount = Field(default_factory=lambda: ObservedCount(status="unavailable"))


class ObservedCost(ActivityValue):
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    status: Literal["observed", "partial", "unavailable"]
    source: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.status == "unavailable":
            if self.amount is not None or self.currency is not None:
                raise ValueError("Unavailable cost has no amount or currency")
        elif self.amount is None or self.currency is None or not self.source:
            raise ValueError("Observed cost requires amount, currency and its recorded source")
        return self


class ModelActivityCounts(ActivityValue):
    input_tokens: ObservedCount
    output_tokens: ObservedCount
    embedding_tokens: ObservedCount
    cost: ObservedCost
    external_client_consumption: Literal["not_observed"] = "not_observed"


class ActivitySummary(ActivityValue):
    tenant_id: str = Field(min_length=1, max_length=64)
    audience: Literal["personal", "organization_administrators"]
    window: ActivityWindow
    coverage: ActivityCoverage
    knowledge: KnowledgeActivityCounts
    top_projects: list[ProjectActivity] = Field(default_factory=list, max_length=10)
    daily_activity: list[DailyActivity] = Field(default_factory=list, max_length=367)
    mcp: McpActivityCounts
    models: ModelActivityCounts
