# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-bound continuation for conversation metadata, without imported totals."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, field_validator

from koinon.assistants.dtos import KnowledgeScope
from koinon.integrations.content_sources.read_dtos import ReaderSourceSelection, validate_selections


class HistoryBrowseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    q: str = Field(default="", max_length=255)
    page_size: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=128)
    status: Literal["active", "archived", "all"] = "active"
    folder_id: str | None = Field(default=None, max_length=64)
    workspace_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=64)
    unfiled: bool = False
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)

    @field_validator("reader_source_connections")
    @classmethod
    def valid_choices(cls, values):
        if values is not None:
            validate_selections(values)
        return values


class HistoryThreadOutput(BaseModel):
    id: str
    title: str
    title_source: Literal["default", "manual", "ai"]
    revision: int
    folder_id: str | None
    archived_at: AwareDatetime | None
    scope: KnowledgeScope
    created_at: AwareDatetime
    updated_at: AwareDatetime


class HistoryBrowsePage(BaseModel):
    items: list[HistoryThreadOutput]
    next_cursor: str | None = None
    total: None = None
    total_is_exact: Literal[False] = False


class MessageBrowseInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_size: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=128)
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)

    @field_validator("reader_source_connections")
    @classmethod
    def valid_choices(cls, values):
        if values is not None:
            validate_selections(values)
        return values


class MessageBrowsePage(BaseModel):
    items: list[dict[str, JsonValue]]
    next_cursor: str | None = None
    total: None = None
    total_is_exact: Literal[False] = False
