# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/assistants/history/browse_dtos.py
SHA256: 117de683773b5f907f127fdbe8e426783c90d699d921c94fc5da0377e069c06b

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue

from koinon_sdk._base import InputModel, ResponseModel
from koinon_sdk.models import KnowledgeScope
from koinon_sdk.reader_sources import ReaderSourceSelection


class HistoryBrowseInput(InputModel):
    q: str = Field(default="", max_length=255)
    page_size: int = Field(default=25, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=128)
    status: Literal["active", "archived", "all"] = "active"
    folder_id: str | None = Field(default=None, max_length=64)
    workspace_id: str | None = Field(default=None, max_length=64)
    project_id: str | None = Field(default=None, max_length=64)
    unfiled: bool = False
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)


class HistoryThreadOutput(ResponseModel):
    id: str
    title: str
    title_source: Literal["default", "manual", "ai"]
    revision: int
    folder_id: str | None
    archived_at: AwareDatetime | None
    scope: KnowledgeScope
    created_at: AwareDatetime
    updated_at: AwareDatetime


class HistoryBrowsePage(ResponseModel):
    items: list[HistoryThreadOutput]
    next_cursor: str | None = None
    total: None = None
    total_is_exact: Literal[False] = False


class MessageBrowseInput(InputModel):
    page_size: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, max_length=128)
    reader_source_connections: list[ReaderSourceSelection] | None = Field(default=None, max_length=100)


class MessageBrowsePage(ResponseModel):
    items: list[dict[str, JsonValue]]
    next_cursor: str | None = None
    total: None = None
    total_is_exact: Literal[False] = False
