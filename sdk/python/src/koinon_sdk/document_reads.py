# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/document_history/read_dtos.py
SHA256: c3dcb83ed5296c75e4930364c8f37ee089b04aa550262c38a7561575e9025f97

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import Field

from koinon_sdk.reader_sources import ReaderPageInput, ReaderReadInput


class DocumentPartsReadInput(ReaderPageInput):
    kind: Literal["artifact", "section", "chunk", "page"] | None = None


class DocumentChunksReadInput(ReaderReadInput):
    offset: int = Field(default=0, ge=0, strict=True)
    limit: int = Field(default=50, ge=1, le=100, strict=True)
    page: int | None = Field(default=None, ge=1, strict=True)
    section: str | None = Field(default=None, max_length=512)
    q: str | None = Field(default=None, max_length=255)


class LineageReadInput(ReaderReadInput):
    asset_id: str | None = Field(default=None, min_length=1, max_length=64)
