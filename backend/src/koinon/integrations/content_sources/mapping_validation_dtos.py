# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Browser-owned preparation contracts. Preparation never authorizes import."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.knowledge.bulk.dtos import Digest, Identifier, Input, Output

ValidationState = Literal[
    "scanning",
    "verifying",
    "checking_changes",
    "complete",
    "blocked",
    "stale",
    "cleaning",
    "abandoned",
    "expired",
]
ValidationReason = Literal[
    "SOURCE_NAME_COLLISION",
    "SOURCE_DESTINATION_COLLISION",
    "SOURCE_LOCAL_EDIT",
    "SOURCE_CHANGED",
    "SOURCE_AUTHORITY_CHANGED",
    "SOURCE_SCAN_LIMIT_EXCEEDED",
    "SOURCE_VALIDATION_CAPACITY",
    "SOURCE_UNAVAILABLE",
    "SOURCE_VALIDATION_REFRESH_REQUIRED",
    "SOURCE_INVALID_SELECTION",
]


class SourceMappingValidationInput(MappingReviewInput):
    operation_id: UUID
    mapping_id: Identifier | None = None
    expected_revision: int | None = Field(default=None, strict=True, ge=1)

    @model_validator(mode="after")
    def mapping_revision_pair(self):
        if (self.mapping_id is None) != (self.expected_revision is None):
            raise ValueError("An existing mapping requires its expected revision")
        return self

    def selection(self) -> MappingReviewInput:
        return MappingReviewInput.model_validate(
            self.model_dump(exclude={"operation_id", "mapping_id", "expected_revision"})
        )


class SourceMappingValidationContinueInput(Input):
    expected_revision: int = Field(strict=True, ge=1)
    continuation_token: str = Field(strict=True, min_length=1, max_length=4096)


class SourceMappingValidationAbandonInput(Input):
    expected_revision: int = Field(strict=True, ge=1)


class SourceMappingValidationOutput(Output):
    validation_id: UUID
    revision: int
    state: ValidationState
    expires_at: datetime
    continuation_token: str | None = None
    enumeration_complete: bool
    observed_count: int | None = None
    total: int | None = None
    manifest_sha256: Digest | None = None
    reason_code: ValidationReason | None = None


class SourceMappingValidationItem(Output):
    item_id: str
    name: str
    kind: Literal["file", "folder", "shortcut"]
    version: str | None
    filename: str
    export_mime: str | None
    reason: str | None
    relative_path: list[str]
    destination_relative_path: list[str]
    size_bytes: int | None
    collision: Literal["none", "source_name", "destination_name", "local_edit"]
    action: Literal["create", "replace", "move", "skip"]


class SourceMappingValidationItemPage(Output):
    validation_id: UUID
    revision: int
    items: list[SourceMappingValidationItem]
    visible_count: int
    next_cursor: str | None
    total: int | None = None
