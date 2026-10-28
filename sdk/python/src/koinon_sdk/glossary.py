# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Structured glossary wire fields; revision timestamps remain unparsed strings.

Derived from packages/structured/src/flyquery/interfaces/glossary.py.
Original wire contracts copyright 2024-2026 Firefly Software Foundation.
"""

from typing import Annotated

from pydantic import ConfigDict, Field

from koinon_sdk._base import InputModel, ResponseModel

GlossaryText = Annotated[str, Field(max_length=512)]


class GlossaryTermCreate(InputModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    term: str = Field(min_length=1, max_length=512)
    definition: str = Field(min_length=1, max_length=16000)
    synonyms_json: list[GlossaryText] = Field(
        default_factory=list[GlossaryText], alias="synonyms", max_length=64
    )
    tags_json: list[GlossaryText] = Field(default_factory=list[GlossaryText], alias="tags", max_length=64)
    related_columns_json: list[GlossaryText] = Field(
        default_factory=list[GlossaryText], alias="related_columns", max_length=64
    )
    related_metrics_json: list[GlossaryText] = Field(
        default_factory=list[GlossaryText], alias="related_metrics", max_length=64
    )


class GlossaryTermUpdate(InputModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    definition: str | None = Field(default=None, max_length=16000)
    synonyms_json: list[GlossaryText] | None = Field(default=None, alias="synonyms", max_length=64)
    tags_json: list[GlossaryText] | None = Field(default=None, alias="tags", max_length=64)
    related_columns_json: list[GlossaryText] | None = Field(
        default=None, alias="related_columns", max_length=64
    )
    related_metrics_json: list[GlossaryText] | None = Field(
        default=None, alias="related_metrics", max_length=64
    )


class GlossaryTermRead(ResponseModel):
    id: str
    tenant_id: str
    workspace_id: str
    term: str
    definition: str
    synonyms_json: list[str]
    tags_json: list[str]
    related_columns_json: list[str]
    related_metrics_json: list[str]
    created_at: str
    updated_at: str


class GlossaryPage(ResponseModel):
    items: list[GlossaryTermRead]
    total: int | None = None
    limit: int | None = None
    offset: int | None = None
    has_more: bool | None = None
