# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable historical identities; retained content requires an exact part read."""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon.evidence.dtos import Frozen, Identifier, Revision


class DocumentHistoryIdentity(Frozen):
    document_id: Identifier
    catalog_source_id: Identifier
    native_source_id: Identifier


class DocumentVersion(DocumentHistoryIdentity):
    source_version_id: Identifier
    filename: str | None = Field(default=None, max_length=512)
    media_type: str | None = Field(default=None, max_length=128)
    sha256: Revision
    byte_size: int = Field(ge=0)
    actor: str | None = Field(default=None, max_length=512)
    created_at: AwareDatetime
    predecessor_source_version_id: Identifier | None = None


class DocumentExtraction(DocumentHistoryIdentity):
    source_version_id: Identifier
    extraction_id: Identifier
    purpose: str = Field(min_length=1, max_length=32)
    coverage: str = Field(min_length=1, max_length=32)
    normalized_sha256: Revision
    created_at: AwareDatetime
    predecessor_extraction_id: Identifier | None = None


class DocumentPartSummary(DocumentHistoryIdentity):
    source_version_id: Identifier
    extraction_id: Identifier
    source_part_id: Identifier
    kind: Literal["artifact", "section", "chunk", "page"]
    ordinal: int = Field(ge=0)
    sha256: Revision
    recorded_page: int | None = Field(default=None, ge=1)
    page_basis: Literal["recorded_loader"] | None = None
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    offset_basis: str | None = Field(default=None, max_length=64)
    created_at: AwareDatetime


class DocumentPartContent(DocumentHistoryIdentity):
    source_version_id: Identifier
    extraction_id: Identifier
    source_part_id: Identifier
    kind: Literal["chunk", "page"]
    sha256: Revision
    text: str = Field(max_length=1_000_000)
    recorded_page: int | None = Field(default=None, ge=1)
    page_basis: Literal["recorded_loader"]
    raw_sha256: Revision
    normalized_sha256: Revision
    input_sha256: Revision


class DocumentHistoryPagination(Frozen):
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool


class DocumentVersionPage(DocumentHistoryPagination):
    items: tuple[DocumentVersion, ...] = Field(max_length=100)


class DocumentExtractionPage(DocumentHistoryPagination):
    items: tuple[DocumentExtraction, ...] = Field(max_length=100)


class DocumentPartPage(DocumentHistoryPagination):
    items: tuple[DocumentPartSummary, ...] = Field(max_length=100)
