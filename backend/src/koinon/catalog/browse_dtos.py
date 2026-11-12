# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-aware catalog browsing has opaque continuation, never protected totals."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from koinon.catalog.dtos import CatalogEntryOutput, CatalogSummary, MemberActor
from koinon.integrations.content_sources.read_dtos import ReaderSourceSelection


class CatalogBrowseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
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


class CatalogBrowseOutput(BaseModel):
    items: list[CatalogEntryOutput]
    actors: dict[str, MemberActor]
    next_cursor: str | None
    summaries: dict[str, CatalogSummary] = Field(default_factory=dict)
    total: None = None
    total_is_exact: Literal[False] = False
