# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class OrganizationChatSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str
    default_agent_id: str | None
    revision: int = Field(ge=0, le=2147483647)
    configured: bool
    can_run: bool
    status: Literal["unconfigured", "unavailable", "disabled", "needs_setup", "unverified", "ready"]


class OrganizationChatSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_agent_id: str | None = Field(max_length=64)
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
