# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/catalog/browse_dtos.py
SHA256: 70c6168d42c77b9a9eaba90498ffa1bea8def5b8e7e6ac5962b7178d1dd9e0ac

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import Field

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.models import AuthorSummary, CatalogEntry, CatalogSummary
from koinon_sdk.reader_sources import ReaderSourceSelection


class CatalogBrowseInput(InputModel):
    parent_id: str | None = Field(default=None, max_length=64)
    workspace_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=64)
    kind: str | None = Field(default=None, max_length=32)
    include_archived: bool = False
    view: Literal["raw", "library"] = "library"
    q: str = Field(default="", max_length=255)
    status: str | None = Field(default=None, max_length=32)
    format: str | None = Field(default=None, max_length=32)
    tag: str | None = Field(default=None, max_length=64)
    page_size: int = Field(default=50, ge=1, le=100)
    sort: Literal["name", "kind", "created_at", "updated_at"] = "name"
    order: Literal["asc", "desc"] = "asc"
    cursor: str | None = Field(default=None, min_length=43, max_length=43)
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)


class CatalogBrowseOutput(ResponseModel):
    items: list[CatalogEntry]
    actors: dict[str, AuthorSummary]
    next_cursor: str | None
    summaries: dict[str, CatalogSummary] = Field(default_factory=dict[str, CatalogSummary])
    total: None = None
    total_is_exact: Literal[False] = False
