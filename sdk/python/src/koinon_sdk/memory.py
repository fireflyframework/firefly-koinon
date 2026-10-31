# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/assistants/memory/dtos.py
SHA256: 7d4a2594885de71bad22720f951a3ca58fdadcb534ccd8c594a01c080f178626

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import ResponseModel
from koinon_sdk.organization_chat import OrganizationMemoryPolicy


class MemoryValue(ResponseModel):
    pass


class MemoryTurnReference(MemoryValue):
    run_id: str = Field(min_length=1, max_length=64)
    generation_id: str | None = Field(default=None, min_length=1, max_length=64)
    thread_id: str = Field(min_length=1, max_length=64)
    conversation_title: str = Field(min_length=1, max_length=160)
    user_created_at: AwareDatetime
    user_message_id: str = Field(min_length=1, max_length=64)
    user_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    answer_message_id: str = Field(min_length=1, max_length=64)
    answer_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    answer_included: bool = False
    availability: Literal[
        "available", "archived", "deleted", "moved", "memory_disabled", "changed", "unverified"
    ] = "available"


class MemoryReceipt(MemoryValue):
    validation_mode: Literal["generation", "historical_replay"] = "generation"
    generation_id: str = Field(min_length=1, max_length=64)
    policy_version: Literal[1] = 1
    mode: Literal["current_thread", "personal_project"]
    folder_id: str | None = Field(default=None, min_length=1, max_length=64)
    folder_revision: int | None = Field(default=None, ge=1, le=2147483647)
    scope_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    manifest_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    organization_policy_revision: int = Field(ge=0, le=2147483647)
    effective_policy: OrganizationMemoryPolicy
    turns: tuple[MemoryTurnReference, ...] = Field(default=(), max_length=20)
    dependency_count: int = Field(ge=0, le=128)
    context_available: bool = True
    unavailable_dependency_count: int = Field(default=0, ge=0, le=128)
    created_at: AwareDatetime
