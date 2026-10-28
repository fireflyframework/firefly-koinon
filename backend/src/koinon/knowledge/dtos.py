# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DocumentRevisionPreconditions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_source_version_id: UUID | None = None
    expected_extraction_id: UUID | None = None

    @model_validator(mode="after")
    def paired(self):
        if (self.expected_source_version_id is None) != (self.expected_extraction_id is None):
            raise ValueError("Supply the exact source version and extraction together")
        return self


class SearchInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=8000)
    workspace_id: str | None = None
    project_id: str | None = None
    collection_id: str | None = None
    asset_ids: list[Annotated[str, Field(min_length=1, max_length=64)]] | None = Field(
        default=None, max_length=128
    )
    limit: int = Field(default=10, ge=1, le=100)
    answer: bool = False


class QueryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=64)
    question: str = Field(default="", max_length=8000)
    conversation_id: str | None = None
    sql: str | None = Field(default=None, min_length=1, max_length=65536)


class DocumentReingestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    acknowledge_chunk_invalidation: bool = False


class TableReingestInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
