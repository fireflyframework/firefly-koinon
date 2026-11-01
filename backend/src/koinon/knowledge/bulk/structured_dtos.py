# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NativeValue(BaseModel, frozen=True):
    model_config = ConfigDict(extra="forbid", frozen=True)


class StructuredOperationIdentity(NativeValue, frozen=True):
    operation_id: UUID
    tenant_id: str = Field(min_length=1, max_length=512)
    workspace_id: UUID
    dataset_id: UUID
    file_id: UUID
    actor: str = Field(min_length=1, max_length=512)
    catalog_source_id: str = Field(min_length=1, max_length=64)
    catalog_dataset_id: str = Field(min_length=1, max_length=64)
    catalog_file_version_id: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(strict=True, ge=1, le=134217728)


class StructuredTablePlan(NativeValue, frozen=True):
    ordinal: int = Field(strict=True, ge=0, le=15)
    table_id: UUID
    snapshot_id: UUID
    name: str = Field(min_length=1, max_length=255)
    catalog_table_id: str | None = Field(default=None, min_length=1, max_length=64)


class PreparedStructuredTable(StructuredTablePlan, frozen=True):
    catalog_table_id: str = Field(min_length=1, max_length=64)
    lineage_run_id: UUID
    n_columns: int = Field(strict=True, ge=1, le=10000)
    n_rows_actual: int = Field(strict=True, ge=0)
    parquet_key: str = Field(min_length=1, max_length=2048, repr=False)
    parquet_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    parquet_byte_size: int = Field(strict=True, ge=1, le=64 * 1024 * 1024)
    schema_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class StructuredCommitReceipt(NativeValue, frozen=True):
    file_id: UUID
    dataset_id: UUID
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(strict=True, ge=1, le=134217728)
    object_key: str = Field(min_length=1, max_length=2048, repr=False)
    tables: tuple[PreparedStructuredTable, ...] = Field(min_length=1, max_length=16)


class StructuredOperationState(NativeValue, frozen=True):
    identity: StructuredOperationIdentity
    status: Literal["admitted", "prepared", "committed"]
    plan: tuple[StructuredTablePlan, ...] = ()
    prepared: tuple[PreparedStructuredTable, ...] = ()
    receipt: StructuredCommitReceipt | None = Field(default=None, repr=False)


TablePlans = Annotated[tuple[StructuredTablePlan, ...], Field(min_length=1, max_length=16)]
