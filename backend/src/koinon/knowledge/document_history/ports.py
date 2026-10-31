# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact scoped history records, independent of HTTP and SQL implementation."""

from datetime import datetime
from typing import Literal, Protocol, TypedDict, Unpack

from flycanon.core.services.sources.lineage.dtos import VerifiedOriginal


class DocumentReadScope(TypedDict):
    tenant_id: str
    workspace_id: str
    source_id: str
    actor: str


class VersionRecord(TypedDict):
    source_version_id: str
    filename: str | None
    media_type: str | None
    sha256: str
    byte_size: int
    actor: str | None
    created_at: datetime
    predecessor_source_version_id: str | None


class ExtractionRecord(TypedDict):
    source_version_id: str
    extraction_id: str
    purpose: str
    coverage: str
    normalized_sha256: str
    created_at: datetime
    predecessor_extraction_id: str | None


class PartRecord(TypedDict):
    source_version_id: str
    extraction_id: str
    source_part_id: str
    kind: Literal["artifact", "section", "chunk", "page"]
    ordinal: int
    sha256: str
    recorded_page: int | None
    page_basis: Literal["recorded_loader"] | None
    char_start: int | None
    char_end: int | None
    offset_basis: str | None
    created_at: datetime


class PartContentRecord(TypedDict):
    source_version_id: str
    extraction_id: str
    source_part_id: str
    kind: Literal["chunk", "page"]
    sha256: str
    text: str
    recorded_page: int | None
    page_basis: Literal["recorded_loader"]
    raw_sha256: str
    normalized_sha256: str
    input_sha256: str


class HistoryPage[T](TypedDict):
    items: tuple[T, ...]
    total: int
    page: int
    page_size: int
    pages: int
    has_next: bool
    has_previous: bool


class DocumentHistoryPort(Protocol):
    async def versions(
        self, *, page: int = 1, page_size: int = 25, **scope: Unpack[DocumentReadScope]
    ) -> HistoryPage[VersionRecord]: ...

    async def version(
        self, *, source_version_id: str, **scope: Unpack[DocumentReadScope]
    ) -> VersionRecord: ...

    async def extractions(
        self,
        *,
        source_version_id: str,
        page: int = 1,
        page_size: int = 25,
        **scope: Unpack[DocumentReadScope],
    ) -> HistoryPage[ExtractionRecord]: ...

    async def parts(
        self,
        *,
        source_version_id: str,
        extraction_id: str,
        kind: str | None = None,
        page: int = 1,
        page_size: int = 25,
        **scope: Unpack[DocumentReadScope],
    ) -> HistoryPage[PartRecord]: ...

    async def part(
        self,
        *,
        source_version_id: str,
        extraction_id: str,
        source_part_id: str,
        **scope: Unpack[DocumentReadScope],
    ) -> PartContentRecord: ...

    async def original(
        self, *, source_version_id: str, max_bytes: int, **scope: Unpack[DocumentReadScope]
    ) -> VerifiedOriginal: ...
