# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/provenance/read_dtos.py
SHA256: b63077e8d305dbdfbf205e97dffe6cf0927ebe13733e97cb11737c910244192d

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import Field

from koinon_sdk._base import ResponseModel
from koinon_sdk.provenance import TableSnapshotSummary
from koinon_sdk.reader_sources import ReaderPageInput, ReaderReadInput


class SnapshotReadInput(ReaderReadInput):
    snapshot_id: str = Field(min_length=1, max_length=64)


class SnapshotPageReadInput(ReaderPageInput):
    snapshot_id: str = Field(min_length=1, max_length=64)


class SnapshotHistoryReadInput(ReaderReadInput):
    cursor: str | None = Field(default=None, pattern="^[A-Za-z0-9_-]{43}$")
    page_size: int = Field(default=25, strict=True, ge=1, le=100)


class TableSnapshotReadPage(ResponseModel):
    items: tuple[TableSnapshotSummary, ...]
    next_cursor: str | None
    total: None = None
    pages: None = None
    total_is_exact: Literal[False] = False
    current_snapshot_id: str | None = None
