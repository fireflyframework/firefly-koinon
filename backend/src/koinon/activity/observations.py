# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Minimal internal observations from verified native MCP request execution."""

from typing import Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from koinon.activity.dtos import ActivityValue


class McpObservation(ActivityValue):
    observation_id: UUID
    tenant_id: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=512, repr=False)
    workspace_id: str | None = Field(default=None, min_length=1, max_length=64)
    kind: Literal["request", "tool"]
    operation: str = Field(pattern=r"^(?:GET|POST|DELETE|koinon_[a-z0-9_]{1,72})$")
    outcome: Literal["succeeded", "failed", "rejected", "cancelled"]
    duration_ms: int = Field(strict=True, ge=0, le=86400000)

    @model_validator(mode="after")
    def operation_matches_kind(self) -> Self:
        if (self.kind == "tool") != self.operation.startswith("koinon_"):
            raise ValueError("MCP request methods and tool invocations are distinct observations")
        return self
