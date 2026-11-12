# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native immutable identities; binary content stays behind native ports."""

import builtins
import re
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class SourcePublicationBinding:
    """Exact immutable producer evidence; this value does not grant authorization."""

    attempt_id: str
    descriptor_sha256: str
    schema: str = field(default="koinon.source-publication-binding.v1", init=False)

    def __post_init__(self):
        if (
            type(self.attempt_id) is not str
            or not 1 <= len(self.attempt_id) <= 64
            or any(ord(character) < 33 or ord(character) > 126 for character in self.attempt_id)
            or type(self.descriptor_sha256) is not str
            or re.fullmatch(r"[a-f0-9]{64}", self.descriptor_sha256) is None
        ):
            raise ValueError("A bounded source attempt and lowercase publication digest are required")


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
