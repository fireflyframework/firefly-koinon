# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native immutable identities; binary content stays behind native ports."""

import builtins
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class DocumentScope:
    tenant_id: str
    workspace_id: str
    actor: str


@dataclass(frozen=True)
class Admission:
    source_id: str
    version_id: str
    artifact_id: str
    sha256: str
    bytes: int
    object_key: str = field(repr=False)
    expected_version_id: str | None = None
    expected_extraction_id: str | None = None


@dataclass(frozen=True)
class VerifiedOriginal:
    version_id: str
    sha256: str
    bytes: int
    filename: str | None
    media_type: str | None
    content: builtins.bytes = field(repr=False)


@dataclass(frozen=True)
class OriginalFileReceipt:
    version_id: str | None
    sha256: str
    bytes: int
    filename: str | None
    media_type: str | None
    anchor: str


@dataclass(frozen=True)
class LineagePage:
    items: tuple[dict[str, Any], ...]
    total: int
    page: int
    page_size: int
    pages: int


@dataclass(frozen=True)
class ExtractedPage:
    part_id: str
    text: str = field(repr=False)
    sha256: str
    page: int | None
    page_basis: Literal["recorded_loader"]
    source_sections: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class WholeDocumentRead:
    source_id: str
    source_version_id: str
    extraction_id: str
    ingestion_extraction_id: str
    input_artifact_id: str
    input_sha256: str
    normalized_artifact_id: str
    normalized_sha256: str
    raw_sha256: str
    pages: tuple[ExtractedPage, ...] = field(repr=False)


@dataclass(frozen=True)
class DocumentReadPin:
    source_id: str
    source_version_id: str
    ingestion_extraction_id: str
    filename: str | None
    kind: str
    raw_sha256: str
    raw_bytes: int
    normalized_sha256: str


@dataclass(frozen=True)
class WholeDocumentPart:
    part_id: str
    source_id: str
    source_version_id: str
    extraction_id: str
    ingestion_extraction_id: str
    text: str = field(repr=False)
    sha256: str
    page: int | None
    page_basis: Literal["recorded_loader"]
    source_sections: tuple[tuple[str, str], ...]
    raw_sha256: str
    normalized_sha256: str
    input_sha256: str


@dataclass(frozen=True)
class DocumentCitationRef:
    source_id: str
    source_version_id: str
    extraction_id: str
    part_id: str
    sha256: str
    recorded_page: int | None
    page_basis: Literal["recorded_loader"]
