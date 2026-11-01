# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/external_reviews/file_dtos.py
SHA256: a787949e95a94b7432e48cc51898b0d7405f4f50e2de9ceb3824530dc7627e70

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue

from koinon_sdk._base import InputModel
from koinon_sdk.curated import Frozen, Identifier, KnowledgeDestination, Sha256

CHUNK_BYTES = 65536
MAX_FILE_BYTES = 128 * 1024 * 1024


class ExternalFileReviewInput(InputModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=128)
    mode: Literal["document", "dataset"]
    destination_id: Identifier
    size_bytes: int = Field(ge=1, le=MAX_FILE_BYTES, strict=True)
    sha256: Sha256


class ExternalFileChunkInput(InputModel):
    index: int = Field(ge=0, le=2047, strict=True)
    data_base64: str = Field(min_length=4, max_length=87384)
    sha256: Sha256


class ExternalFileCatalogEntry(Frozen):
    id: Identifier
    tenant_id: Identifier
    kind: str
    name: str
    parent_id: Identifier | None
    workspace_id: Identifier
    project_id: Identifier | None
    description: str
    status: str
    created_by: str
    updated_by: str
    metadata: dict[str, JsonValue]
    created_at: AwareDatetime
    updated_at: AwareDatetime


class ExternalFileReceipt(Frozen):
    source: ExternalFileCatalogEntry
    assets: tuple[ExternalFileCatalogEntry, ...] = Field(min_length=1, max_length=128)


class ExternalFileReviewView(Frozen):
    id: Identifier
    tenant_id: Identifier
    revision: int = Field(ge=1)
    authorization_digest: Sha256
    status: Literal["uploading", "preview", "ingesting", "committed", "cancelled", "unresolved"]
    filename: str
    content_type: str | None
    mode: Literal["document", "dataset"]
    size_bytes: int
    sha256: Sha256
    destination: KnowledgeDestination
    received_chunks: int
    total_chunks: int
    expires_at: AwareDatetime
    submitted_by: str
    credential_id: Identifier
    application_id: Identifier | None
    origin: Literal["external_proposal"] = "external_proposal"
    authority: Literal["unverified"] = "unverified"
    provider: None = None
    model: None = None
    source_id: Identifier | None = None
    intake_status: str | None = None
    receipt: ExternalFileReceipt | None = None


class ExternalFileCleanupInput(InputModel):
    review_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=25)
    max_objects: int = Field(default=32, ge=1, le=64, strict=True)


class ExternalFileCleanupReview(Frozen):
    id: Identifier
    status: Literal["purging", "purged"]
    processed_objects: int = Field(ge=0, le=2049)
    total_objects: int = Field(ge=1, le=2049)


class ExternalFileCleanupResult(Frozen):
    reviews: tuple[ExternalFileCleanupReview, ...] = Field(max_length=25)
