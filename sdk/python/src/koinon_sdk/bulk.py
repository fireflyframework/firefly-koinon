# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/bulk/dtos.py
SHA256: b62365ef5c9327a5d5acaac23f70b30b1a2ebc6f18c721f32a522e939b993669

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel

Identifier = Annotated[str, Field(strict=True, min_length=1, max_length=64)]
Digest = Annotated[str, Field(strict=True, pattern="^[a-f0-9]{64}$")]
ItemStatus = Literal[
    "awaiting_upload", "staged", "queued", "running", "succeeded", "failed", "cancelled", "reconciling"
]
BatchStatus = Literal[
    "expired", "staging", "queued", "running", "succeeded", "partial", "failed", "cancelled", "reconciling"
]


class Input(InputModel):
    pass


class BulkDestination(Input):
    workspace_id: Identifier
    project_id: Identifier
    parent_id: Identifier


class FileManifestItem(Input):
    client_item_id: Identifier
    filename: str = Field(strict=True, min_length=1, max_length=255)
    mode: Literal["document", "dataset"]
    size_bytes: int = Field(strict=True, ge=1, le=128 * 1024 * 1024)
    sha256: Digest


class FileBatchCreate(Input):
    destination: BulkDestination
    processing_policy: Literal["extract_only_v1"] = "extract_only_v1"
    items: list[FileManifestItem] = Field(min_length=1, max_length=100)


class BulkAction(Input):
    expected_revision: int = Field(strict=True, ge=1, le=2147483647)


RecoveryOperation = Literal["retry_processing", "finalize_publication", "acknowledge_commit"]


class BulkRecoveryAction(BulkAction):
    operation: RecoveryOperation


class Output(ResponseModel):
    pass


NativeRecoveryState = Literal["absent", "admitted", "prepared", "committed", "unknown", "not_checked"]


class FileRecoveryView(Output):
    batch_id: Identifier
    item_id: Identifier
    batch_revision: int = Field(ge=1, le=2147483647)
    native_state: NativeRecoveryState
    operation: RecoveryOperation | None
    reason_code: str | None = Field(default=None, max_length=64)
    attempts: int = Field(ge=0, le=2147483647)
    max_attempts: int = Field(ge=1, le=2147483647)
    checked_at: datetime | None
    job_status: Literal["queued", "running", "succeeded", "failed", "cancelled", "unknown"]
    original_receipt_state: Literal["verified", "unavailable", "not_checked"]


class FileBatchCapabilities(Output):
    configured: bool
    modes: list[Literal["document", "dataset"]]
    processing_policy: Literal["extract_only_v1"] = "extract_only_v1"
    staging_backend: Literal["private_local_posix", "private_azure_blob", "private_gcs_object"] = (
        "private_local_posix"
    )
    staging_topology: Literal["single_host_shared_durable_posix", "shared_private_object_store"] = (
        "single_host_shared_durable_posix"
    )
    writer_fence: Literal["primary_database_generation_lease"] = "primary_database_generation_lease"
    worker: Literal["external_native_worker"] = "external_native_worker"
    automatic_unknown_replay: Literal[False] = False
    synchronous_max_file_bytes: int = 32 * 1024 * 1024
    large_file_transport: Literal["queued_file_spool"] = "queued_file_spool"
    quota_semantics: Literal["lifetime_admission_bytes"] = "lifetime_admission_bytes"
    max_files: int
    max_file_bytes: int
    max_batch_bytes: int
    max_active_batches_per_subject: int


class FileBatchItemView(Output):
    id: str
    client_item_id: str
    filename: str
    mode: Literal["document", "dataset"]
    size_bytes: int
    sha256: str
    status: ItemStatus
    source_id: str
    asset_id: str
    job_id: str | None
    file_version_id: str | None = None
    table_ids: list[str] = Field(default_factory=list[str])
    source_version_id: str | None = None
    extraction_id: str | None = None
    error_code: str | None = None


class FileBatchView(Output):
    id: str
    tenant_id: str
    destination: BulkDestination
    status: BatchStatus
    revision: int = Field(ge=1, le=2147483647)
    total_items: int
    total_bytes: int
    counts: dict[ItemStatus, int]
    cancellation_requested: bool
    created_at: datetime
    expires_at: datetime


class FileItemPage(Output):
    items: list[FileBatchItemView]
    total: int
    page: int
    page_size: int
    pages: int


class FileBatchPage(Output):
    items: list[FileBatchView]
    total: int
    page: int
    page_size: int
    pages: int


class StagedFileReceipt(Output):
    receipt_id: str
    batch_id: str
    item_id: str
    sha256: str
    size_bytes: int
    status: Literal["staged"] = "staged"
