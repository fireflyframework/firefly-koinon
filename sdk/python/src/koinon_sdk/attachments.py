# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/attachments/dtos.py
SHA256: fe244915be28e6501bf352fed5eb9299931e421185bbf0ca4dd155f738c2155c

Server authorization and semantic validation remain authoritative.
"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import Field, JsonValue, RootModel

from koinon_sdk._base import DocumentRevisionPreconditions, InputModel, ResponseModel

AttachmentStatus = Literal[
    "storing", "queued", "extracting", "ready", "failed", "cancelled", "expired", "deleted"
]
AttachmentKind = Literal["document", "image", "bundle"]


class AttachmentProgress(ResponseModel):
    status: Literal["storing", "queued", "running", "succeeded", "failed", "cancelled"]
    percent: int = Field(ge=0, le=100)
    attempts: int = Field(ge=0)


class AttachmentView(ResponseModel):
    id: str
    tenant_id: str
    thread_id: str
    filename: str
    media_type: str
    kind: AttachmentKind
    size_bytes: int
    sha256: str
    status: AttachmentStatus
    revision: int
    created_at: datetime
    expires_at: datetime
    page_count: int | None = None
    chunk_count: int
    progress: AttachmentProgress
    error_code: str | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list[str])


class AttachmentPage(ResponseModel):
    items: list[AttachmentView]
    total: int
    page: int
    page_size: int
    pages: int


class PrivateChunkView(ResponseModel):
    id: str
    attachment_id: str
    index: int
    text: str
    page: int | None = None
    section_path: list[str]
    char_start: int
    char_end: int
    offset_basis: Literal["normalized_text_code_points"] = "normalized_text_code_points"
    sha256: str


class PrivateChunkPage(ResponseModel):
    items: list[PrivateChunkView]
    total: int
    page: int
    page_size: int
    pages: int


class AttachmentRevision(InputModel):
    expected_revision: int = Field(ge=1, strict=True)


class AddKnowledge(AttachmentRevision):
    action: Literal["add"]
    mode: Literal["document", "dataset"]
    workspace_id: str = Field(min_length=1, max_length=64)
    project_id: str = Field(min_length=1, max_length=64)
    parent_id: str = Field(min_length=1, max_length=64)


class ReplaceDocument(AttachmentRevision, DocumentRevisionPreconditions):
    action: Literal["replace_document"]
    document_id: str = Field(min_length=1, max_length=64)
    expected_sha256: str = Field(pattern="^[a-fA-F0-9]{64}$")
    acknowledge_chunk_invalidation: bool = Field(strict=True)


class ReplaceTable(AttachmentRevision):
    action: Literal["replace_table"]
    dataset_id: str = Field(min_length=1, max_length=64)
    table_id: str = Field(min_length=1, max_length=64)
    expected_snapshot_id: str = Field(min_length=1, max_length=64)


PromotionAction = Annotated[AddKnowledge | ReplaceDocument | ReplaceTable, Field(discriminator="action")]


class AttachmentPromotionInput(RootModel[PromotionAction]):
    pass


class AttachmentObservation(ResponseModel):
    available: bool | None
    reason: str


class AttachmentLimits(ResponseModel):
    max_file_bytes: int
    max_image_bytes: int
    max_selected: int
    max_thread_files: int
    max_thread_bytes: int
    max_model_text_chars: int
    max_model_binary_bytes: int
    extraction_timeout_seconds: int
    ttl_seconds: int


class AttachmentFormat(ResponseModel):
    kind: AttachmentKind
    media_type: str
    extensions: list[str]
    extraction: AttachmentObservation


class AttachmentPromotionRequirements(ResponseModel):
    ready_attachment: bool = True
    ingest_write: bool = True
    catalog_write: bool = True
    document_sha256: bool = True
    document_chunk_invalidation_acknowledgement: bool = True
    table_snapshot_id: bool = True


class AttachmentCapabilities(ResponseModel):
    storage: AttachmentObservation
    database: AttachmentObservation
    extraction: AttachmentObservation
    limits: AttachmentLimits
    formats: list[AttachmentFormat]
    promotion: AttachmentPromotionRequirements


class PromotedCatalogEntry(ResponseModel):
    id: str
    tenant_id: str
    kind: str
    name: str
    parent_id: str | None
    workspace_id: str | None
    project_id: str | None
    description: str
    status: str
    created_by: str
    updated_by: str
    metadata: dict[str, JsonValue]
    created_at: datetime
    updated_at: datetime


class AttachmentPromotionView(ResponseModel):
    promotion_id: str
    attachment_id: str
    action: Literal["add", "replace_document", "replace_table"]
    source: PromotedCatalogEntry | None = None
    assets: list[PromotedCatalogEntry] = Field(default_factory=list[PromotedCatalogEntry])
    asset: PromotedCatalogEntry | None = None
    table: PromotedCatalogEntry | None = None
    version: PromotedCatalogEntry | None = None
    effects: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])
