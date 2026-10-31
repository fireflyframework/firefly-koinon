# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema


class OrganizationMemoryPolicyInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    allow_project_memory: bool = True
    max_history_messages: int = Field(default=40, ge=0, le=40)
    max_history_tokens: int = Field(default=8192, ge=0, le=65536)
    max_project_memory_messages: int = Field(default=20, ge=0, le=40)


class OrganizationMemoryPolicy(OrganizationMemoryPolicyInput):
    @model_validator(mode="after")
    def bounded_project(self):
        if self.max_project_memory_messages > self.max_history_messages:
            raise ValueError("Project memory cannot exceed the total conversation history limit")
        return self


class OrganizationChatSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    tenant_id: str
    default_agent_id: str | None
    revision: int = Field(ge=0, le=2147483647)
    configured: bool
    memory: OrganizationMemoryPolicy = Field(default_factory=OrganizationMemoryPolicy)
    can_run: bool
    status: Literal["unconfigured", "unavailable", "disabled", "needs_setup", "unverified", "ready"]


class OrganizationChatSettingsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    default_agent_id: str | None = Field(max_length=64)
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)

    memory: OrganizationMemoryPolicyInput | SkipJsonSchema[None] = None

    @field_validator("memory", mode="before")
    @classmethod
    def memory_nonnull_when_present(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit memory to preserve the current policy")
        return value
