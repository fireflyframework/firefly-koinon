# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/integrations/content_sources/sync_dtos.py
SHA256: d54190838a67601795c75004b8ab3834755b6a579c20f2ff90b88645a4cc8765

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.bulk import Digest
from koinon_sdk.evidence import Identifier
from koinon_sdk.source_mapping import MappingReviewInput

ControlAction = Literal["sync", "pause", "resume", "cancel", "retry", "retire"]
SourceOperationAction = Literal["review", "apply", "sync", "pause", "resume", "cancel", "retry", "retire"]
RunStatus = Literal[
    "queued", "running", "reconciling", "reconnect_required", "succeeded", "partial", "failed", "cancelled"
]


class OperationInput(InputModel):
    operation_id: str = Field(strict=True, min_length=36, max_length=36)


class SourceControlInput(OperationInput):
    expected_revision: int = Field(strict=True, ge=1, le=2147483646)


class SourcePolicyReviewInput(MappingReviewInput, OperationInput):
    validation_id: UUID | None = None


class SourceExistingPolicyReviewInput(SourcePolicyReviewInput):
    expected_revision: int = Field(strict=True, ge=1, le=2147483646)


class SourcePolicyApplyInput(SourceControlInput):
    review_id: Identifier
    review_digest: Digest


class SourcePolicyOperationOutput(ResponseModel):
    schema_name: Literal["koinon.source-policy-operation.v1"] = Field(
        default="koinon.source-policy-operation.v1", alias="schema"
    )
    receipt_id: Identifier
    operation_id: str
    action: Literal["review", "apply"]
    mapping_id: Identifier
    policy_id: Identifier
    expected_policy_revision: int | None
    result_policy_revision: int
    review_digest: Digest
    review_expires_at: datetime
    disposition: Literal["reviewed", "accepted"]


class SourceDestinationSegment(ResponseModel):
    id: Identifier
    kind: str
    name: str = Field(max_length=255)


class SourceDestinationPresentation(ResponseModel):
    segments: list[SourceDestinationSegment] = Field(max_length=256)


class SourceRootPresentation(ResponseModel):
    name: str = Field(max_length=4096)
    relative_path: list[str] = Field(max_length=256)


class SourceMappingPresentation(ResponseModel):
    source_root: SourceRootPresentation | None = None
    destination: SourceDestinationPresentation | None = None
    unavailable_reason: Literal["access_denied", "reconnect_required", "unavailable"] | None = None


class SourcePreviewItem(ResponseModel):
    item_id: str
    name: str
    kind: str
    version: str | None
    filename: str
    export_mime: str | None
    reason: str | None
    ancestry: list[str]
    relative_path: list[str]
    destination_relative_path: list[str]
    collision: Literal["none", "source_name", "destination_name", "local_edit"]
    size_bytes: int | None
    action: Literal["create", "replace", "move", "skip"]


class SourceReviewPage(ResponseModel):
    review_id: Identifier
    validation_id: UUID | None = None
    root_kind: Literal["file", "folder"] = "folder"
    policy_revision: int
    review_digest: Digest
    expires_at: datetime
    items: list[SourcePreviewItem]
    next_cursor: str | None
    enumeration_complete: bool
    total: int | None
    observed_count: int | None
    known_bytes: int | None
    unknown_size_count: int | None
    can_apply: bool
    destination: SourceDestinationPresentation


class SourceControlOutput(ResponseModel):
    operation_id: str
    receipt_id: Identifier
    action: ControlAction
    control_revision: int
    run_id: Identifier | None = None
    disposition: Literal["queued", "paused", "active", "stopping", "reconciling", "retired"]


class SourcePolicyReceipt(ResponseModel):
    kind: Literal["policy"] = "policy"
    receipt: SourcePolicyOperationOutput


class SourceControlReceipt(ResponseModel):
    kind: Literal["control"] = "control"
    receipt: SourceControlOutput


SourceOperationReceipt = Annotated[SourcePolicyReceipt | SourceControlReceipt, Field(discriminator="kind")]


class SourceMappingOutput(ResponseModel):
    id: Identifier
    revision: int
    policy_revision: int | None
    latest_review_revision: int
    control_revision: int | None
    connection_id: Identifier
    policy: MappingReviewInput
    presentation: SourceMappingPresentation
    status: Literal["reviewed", "active", "paused", "reconnect_required", "retired"]
    next_run_at: datetime | None
    can_pause: bool
    can_resume: bool
    can_retire: bool
    can_sync: bool


class SourceRunOutput(ResponseModel):
    id: Identifier
    mapping_id: Identifier
    policy_revision: int
    control_revision: int
    status: RunStatus
    stopping: bool
    retry_of_run_id: Identifier | None
    counters: dict[str, int]
    enumeration_complete: bool
    created_at: datetime
    finished_at: datetime | None
    can_cancel: bool
    can_retry: bool


class SourceRunItem(ResponseModel):
    id: Identifier
    object_id: Identifier
    generation: int = Field(ge=1)
    remote_version: str | None
    kind: Literal["file", "folder", "deleted", "unknown"]
    name: str
    relative_path: list[str]
    status: Literal[
        "observed",
        "downloading",
        "processing",
        "synchronized",
        "searchable",
        "skipped",
        "conflict",
        "retired",
        "failed",
        "indeterminate",
    ]
    error_code: str | None
    source_id: Identifier | None
    asset_id: Identifier | None
    attempt_id: Identifier | None
    updated_at: datetime


class SourceRunItemPage(ResponseModel):
    items: list[SourceRunItem] = Field(max_length=100)
    next_cursor: str | None


class SourceReplacementPreviewInput(InputModel):
    expected_revision: int = Field(strict=True, ge=1, le=2147483646)
    remote_version: str = Field(strict=True, min_length=1, max_length=1024)


class SourcePreviousMember(ResponseModel):
    table_id: str
    catalog_table_id: Identifier
    locator: str = Field(max_length=2048)
    name: str = Field(max_length=255)


class SourceDiscoveredMember(ResponseModel):
    locator: str = Field(max_length=2048)
    name: str = Field(max_length=255)
    ambiguous: bool


class SourceReplacementPreview(ResponseModel):
    object_id: Identifier
    remote_version: str = Field(max_length=1024)
    content_sha256: Digest
    baseline_sha256: Digest
    new_locator_set_sha256: Digest
    parser_fingerprint: str = Field(max_length=128)
    previous_members: list[SourcePreviousMember] = Field(min_length=1, max_length=16)
    new_members: list[SourceDiscoveredMember] = Field(min_length=1, max_length=16)
