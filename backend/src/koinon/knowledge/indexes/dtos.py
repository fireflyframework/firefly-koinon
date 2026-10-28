# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class IndexPlanInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=1, max_length=64)
    domain: Literal["documents", "structured"]
    provider_id: str = Field(min_length=1, max_length=64)
    model_id: str = Field(min_length=1, max_length=255)
    expected_dimensions: int | None = Field(default=None, ge=64, le=4096, strict=True)


class IndexCreateInput(IndexPlanInput):
    expected_active_id: str | None = Field(max_length=64)
    expected_connection_revision: int | None = Field(ge=1, strict=True)
    batch_size: int = Field(default=32, ge=1, le=64, strict=True)


class IndexRevisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1, strict=True)


class IndexActivateInput(IndexRevisionInput):
    expected_active_id: str | None = Field(max_length=64)
    expected_connection_revision: int | None = Field(ge=1, strict=True)

    recovery: Literal["finish", "restore_previous"] | None = None


class NativeIndexChoice(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    domain: Literal["documents", "structured"]
    native_id: str
    space_id: str | None
    provider_kind: str | None
    model_id: str | None
    dimensions: int | None
    storage_dimensions: int
    status: str
    active: bool
    chunk_count: int
    vector_count: int
    indexed: bool | None
    qualification: str
    managed_id: str | None = None
    created_at: str | None = None
    ready_at: str | None = None
    activated_at: str | None = None
    retired_at: str | None = None


class KnowledgeIndexView(BaseModel):
    id: str
    tenant_id: str
    workspace_id: str
    domain: Literal["documents", "structured"]
    native_id: str
    space_id: str
    provider_kind: str
    model_id: str
    dimensions: int
    storage_dimensions: int
    status: str
    active: bool
    revision: int
    job_id: str | None = None
    chunk_count: int
    vector_count: int
    indexed: bool
    qualification: str
    recovery_required: bool = False
    native_status: str | None = None
    provider_id: str | None = None
    created_by: str | None = None
    updated_by: str | None = None
    previous_space_id: str | None = None
    created_at: str | None = None
    ready_at: str | None = None
    activated_at: str | None = None
    retired_at: str | None = None
    error_code: str | None = None
    error: str | None = None


class IndexPage(BaseModel):
    items: list[KnowledgeIndexView]
    total: int
    limit: int
    offset: int


class NativeIndexPage(BaseModel):
    items: list[NativeIndexChoice]
    total: int
    limit: int
    offset: int


class IndexPlanView(BaseModel):
    tenant_id: str
    workspace_id: str
    domain: Literal["documents", "structured"]
    provider_id: str
    provider_kind: str
    provider_revision: int
    model_id: str
    dimensions: int
    storage_dimensions: int
    qualification: str
    expected_connection_revision: int | None
    active_space_id: str | None
    active_index_id: str | None
    chunk_count: int
    warnings: list[str]


class IndexJobView(BaseModel):
    index: KnowledgeIndexView
    job_id: str
