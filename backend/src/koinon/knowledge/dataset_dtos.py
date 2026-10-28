# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class NativeAppendedTable(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    table_id: UUID
    name: str = Field(min_length=1, max_length=255)
    snapshot_id: UUID
    n_columns: int = Field(ge=1)
    n_rows_estimate: int = Field(ge=0)


class NativeDatasetFile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    file_id: UUID
    tables: list[NativeAppendedTable] = Field(min_length=1, max_length=128)

    @model_validator(mode="after")
    def distinct_tables(self):
        if len({table.table_id for table in self.tables}) != len(self.tables):
            raise ValueError("An appended file must contain distinct native tables")
        if len({table.snapshot_id for table in self.tables}) != len(self.tables):
            raise ValueError("An appended file must contain distinct native snapshots")
        return self


class DatasetFileAppendResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    dataset_id: str
    file_version_id: str
    filename: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_size: int = Field(ge=1)
    table_ids: list[str] = Field(min_length=1, max_length=128)
    status: Literal["ready"] = "ready"
