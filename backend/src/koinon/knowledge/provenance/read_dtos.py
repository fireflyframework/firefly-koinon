# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Snapshot selection stays separate from the requesting reader's accounts."""

from typing import Literal

from pydantic import BaseModel, Field

from koinon.integrations.content_sources.read_dtos import ReaderPageInput, ReaderReadInput
from koinon.knowledge.provenance.dtos import TableSnapshotSummary


class SnapshotReadInput(ReaderReadInput):
    snapshot_id: str = Field(min_length=1, max_length=64)


class SnapshotPageReadInput(ReaderPageInput):
    snapshot_id: str = Field(min_length=1, max_length=64)


class SnapshotHistoryReadInput(ReaderReadInput):
    cursor: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{43}$")
    page_size: int = Field(default=25, strict=True, ge=1, le=100)


class TableSnapshotReadPage(BaseModel):
    items: tuple[TableSnapshotSummary, ...]
    next_cursor: str | None
    total: None = None
    pages: None = None
    total_is_exact: Literal[False] = False
    current_snapshot_id: str | None = None
