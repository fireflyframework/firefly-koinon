# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded document read filters with explicit reader intent."""

from typing import Literal

from pydantic import Field

from koinon.integrations.content_sources.read_dtos import ReaderPageInput, ReaderReadInput


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
