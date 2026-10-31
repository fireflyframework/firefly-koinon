# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable personal-context identities, separate from current knowledge evidence."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from koinon.organization_chat.dtos import OrganizationMemoryPolicy


class MemoryValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class MemoryResultPin(MemoryValue):
    id: str = Field(min_length=1, max_length=64)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class MemoryTurnReference(MemoryValue):
    run_id: str = Field(min_length=1, max_length=64)
    generation_id: str | None = Field(default=None, min_length=1, max_length=64)
    thread_id: str = Field(min_length=1, max_length=64)
    conversation_title: str = Field(min_length=1, max_length=160)
    user_created_at: AwareDatetime
    user_message_id: str = Field(min_length=1, max_length=64)
    user_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    answer_message_id: str = Field(min_length=1, max_length=64)
    answer_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    answer_included: bool = False
    availability: Literal[
        "available", "archived", "deleted", "moved", "memory_disabled", "changed", "unverified"
    ] = "available"


class MemoryDependency(MemoryTurnReference):
    scope_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_manifest_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    result_pins: tuple[MemoryResultPin, ...] = Field(default=(), max_length=128)
    attachment_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    origin_token_id: str | None = Field(default=None, min_length=1, max_length=64)


class MemoryManifest(MemoryValue):
    policy_version: Literal[1] = 1
    generation_id: str = Field(min_length=1, max_length=64)
    run_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    subject: str = Field(min_length=1, max_length=512)
    thread_id: str = Field(min_length=1, max_length=64)
    mode: Literal["current_thread", "personal_project"]
    folder_id: str | None = Field(default=None, min_length=1, max_length=64)
    folder_revision: int | None = Field(default=None, ge=1, le=2147483647)
    scope_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    organization_policy_revision: int = Field(ge=0, le=2147483647)
    effective_policy: OrganizationMemoryPolicy
    turns: tuple[MemoryDependency, ...] = Field(default=(), max_length=20)
    dependencies: tuple[MemoryDependency, ...] = Field(default=(), max_length=128)
    input_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    asset_ids: tuple[str, ...] = Field(default=(), max_length=128)
    origin_token_id: str | None = Field(default=None, min_length=1, max_length=64)
    knowledge_scope: dict = Field(default_factory=dict, max_length=4)
    private_context: bool = False
    created_at: AwareDatetime


class MemoryReceipt(MemoryValue):
    validation_mode: Literal["generation", "historical_replay"] = "generation"
    generation_id: str = Field(min_length=1, max_length=64)
    policy_version: Literal[1] = 1
    mode: Literal["current_thread", "personal_project"]
    folder_id: str | None = Field(default=None, min_length=1, max_length=64)
    folder_revision: int | None = Field(default=None, ge=1, le=2147483647)
    scope_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    manifest_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    organization_policy_revision: int = Field(ge=0, le=2147483647)
    effective_policy: OrganizationMemoryPolicy
    turns: tuple[MemoryTurnReference, ...] = Field(default=(), max_length=20)
    dependency_count: int = Field(ge=0, le=128)
    context_available: bool = True
    unavailable_dependency_count: int = Field(default=0, ge=0, le=128)
    created_at: AwareDatetime
