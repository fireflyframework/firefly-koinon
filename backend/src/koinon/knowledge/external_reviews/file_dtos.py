# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue, field_validator, model_validator

from koinon.knowledge.curated.dtos import Frozen, Identifier, KnowledgeDestination, Sha256

CHUNK_BYTES = 65536
MAX_FILE_BYTES = 128 * 1024 * 1024


class ExternalFileReviewInput(Frozen):
    filename: str = Field(min_length=1, max_length=255)
    content_type: str | None = Field(default=None, max_length=128)
    mode: Literal["document", "dataset"]
    destination_id: Identifier
    size_bytes: int = Field(ge=1, le=MAX_FILE_BYTES, strict=True)
    sha256: Sha256

    @field_validator("filename")
    @classmethod
    def safe_filename(cls, value):
        if value in {".", ".."} or any(char in value for char in ("/", "\\", "\0", "\r", "\n")):
            raise ValueError("Use a filename without directory components or control characters")
        return value

    @field_validator("content_type")
    @classmethod
    def safe_type(cls, value):
        if value is not None and (not value.strip() or any(char in value for char in ("\0", "\r", "\n"))):
            raise ValueError("Use a plain declared media type")
        return value


class ExternalFileChunkInput(Frozen):
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

    @model_validator(mode="after")
    def bounded(self):
        if len(json.dumps(self.model_dump(mode="json"), allow_nan=False).encode()) > 65536:
            raise ValueError("The canonical intake receipt exceeds its 64 KiB bound")
        return self


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


class ExternalFileReviewChallenge(Frozen):
    """Private component metadata; not a public API response."""

    review: ExternalFileReviewView
    nonce: str = Field(min_length=43, max_length=43)


class ExternalFileCleanupInput(Frozen):
    review_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=25)
    max_objects: int = Field(default=32, ge=1, le=64, strict=True)

    @field_validator("review_ids")
    @classmethod
    def distinct(cls, value):
        if len(set(value)) != len(value):
            raise ValueError("Select distinct private file reviews")
        return value


class ExternalFileCleanupReview(Frozen):
    id: Identifier
    status: Literal["purging", "purged"]
    processed_objects: int = Field(ge=0, le=2049)
    total_objects: int = Field(ge=1, le=2049)


class ExternalFileCleanupResult(Frozen):
    reviews: tuple[ExternalFileCleanupReview, ...] = Field(max_length=25)
