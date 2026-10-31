# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/organization_chat/dtos.py
SHA256: a1bc02212b0f7faeb0cd71b2954bf64d8983879c49d1955526b36922e5c92c52

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator
from pydantic.json_schema import SkipJsonSchema

from koinon_sdk._base import InputModel, ResponseModel


class OrganizationMemoryPolicyInput(InputModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    allow_project_memory: bool = True
    max_history_messages: int = Field(default=40, ge=0, le=40)
    max_history_tokens: int = Field(default=8192, ge=0, le=65536)
    max_project_memory_messages: int = Field(default=20, ge=0, le=40)


class OrganizationMemoryPolicy(OrganizationMemoryPolicyInput):
    pass

    @model_validator(mode="after")
    def bounded_project(self):
        if self.max_project_memory_messages > self.max_history_messages:
            raise ValueError("Project memory cannot exceed the total conversation history limit")
        return self


class OrganizationChatSettings(ResponseModel):
    tenant_id: str
    default_agent_id: str | None
    revision: int = Field(ge=0, le=2147483647)
    configured: bool
    memory: OrganizationMemoryPolicy = Field(default_factory=OrganizationMemoryPolicy)
    can_run: bool
    status: Literal["unconfigured", "unavailable", "disabled", "needs_setup", "unverified", "ready"]


class OrganizationChatSettingsInput(InputModel):
    default_agent_id: str | None = Field(max_length=64)
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
    memory: OrganizationMemoryPolicyInput | SkipJsonSchema[None] = None

    @field_validator("memory", mode="before")
    @classmethod
    def memory_nonnull_when_present(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit memory to preserve the current policy")
        return value
