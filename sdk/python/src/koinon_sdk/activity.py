# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/activity/dtos.py
SHA256: a4e14f5871e36cfbcf6a8496280b01f0ca3570ead348ae28d1cbbc327d329c81

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel


class ActivityValue(ResponseModel):
    pass


class ActivityWindow(InputModel):
    start_at: datetime
    end_at: datetime
    time_zone: str = Field(min_length=1, max_length=128)


class ObservedCount(ActivityValue):
    value: int | None = Field(default=None, strict=True, ge=0, le=9007199254740991)
    status: Literal["observed", "partial", "unavailable"]
    reason: str | None = Field(default=None, max_length=80)


class ActivityCoverage(ActivityValue):
    observed_since: datetime | None
    complete_window: bool
    missing_observations: int | None = Field(default=None, strict=True, ge=0)
    reasons: list[str] = Field(default_factory=list[str], max_length=10)


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
    local_date: str = Field(pattern="^\\d{4}-\\d{2}-\\d{2}$")
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
    currency: str | None = Field(default=None, pattern="^[A-Z]{3}$")
    status: Literal["observed", "partial", "unavailable"]
    source: str | None = Field(default=None, max_length=120)
    reason: str | None = Field(default=None, max_length=80)


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
    top_projects: list[ProjectActivity] = Field(default_factory=list[ProjectActivity], max_length=10)
    daily_activity: list[DailyActivity] = Field(default_factory=list[DailyActivity], max_length=367)
    mcp: McpActivityCounts
    models: ModelActivityCounts
