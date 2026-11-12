# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/integrations/content_sources/mapping_validation_dtos.py
SHA256: 47522c769e5e46c5f271a232b33e61a38ee8f1ad7e805542a43b049c14a679e5

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.bulk import Digest
from koinon_sdk.evidence import Identifier
from koinon_sdk.source_mapping import MappingReviewInput

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


class SourceMappingValidationContinueInput(InputModel):
    expected_revision: int = Field(strict=True, ge=1)
    continuation_token: str = Field(strict=True, min_length=1, max_length=4096)


class SourceMappingValidationAbandonInput(InputModel):
    expected_revision: int = Field(strict=True, ge=1)


class SourceMappingValidationOutput(ResponseModel):
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


class SourceMappingValidationItem(ResponseModel):
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


class SourceMappingValidationItemPage(ResponseModel):
    validation_id: UUID
    revision: int
    items: list[SourceMappingValidationItem]
    visible_count: int
    next_cursor: str | None
    total: int | None = None
