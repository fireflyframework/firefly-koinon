# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Canonical request, query, and download contracts, independent of the server."""

from dataclasses import dataclass
from typing import Literal, TypedDict

from pydantic import Field, JsonValue

from koinon_sdk._base import DocumentRevisionPreconditions as DocumentRevisionPreconditions
from koinon_sdk.models import CatalogEntry, InputModel, KnowledgeScope, ModelParameters, ResponseModel

Role = Literal["viewer", "analyst", "editor", "operator", "admin"]


class PageFilter(TypedDict, total=False):
    q: str
    page: int
    page_size: int
    sort: str
    order: Literal["asc", "desc"]


class CatalogFilter(PageFilter, total=False):
    format: str
    tag: str
    status: str
    view: Literal["raw", "library"]
    include_archived: bool
    kind: str
    parent_id: str
    project_id: str
    workspace_id: str


class AuditFilter(TypedDict, total=False):
    q: str
    action: str
    subject: str
    from_date: str
    through_date: str
    time_zone: str
    page: int
    page_size: int
    sort: Literal["created_at", "action"]
    order: Literal["asc", "desc"]


class StatusFilter(PageFilter, total=False):
    status: str


class AgentFilter(StatusFilter, total=False):
    workspace_id: str
    project_id: str


class MembershipFilter(TypedDict, total=False):
    q: str
    role: Role
    scope: Literal["all", "tenant", "workspace"]
    workspace_id: str
    page: int
    page_size: int


class InvitationFilter(TypedDict, total=False):
    workspace_id: str
    status: Literal["pending", "accepted", "expired", "revoked"]
    page: int
    page_size: int


class SearchContext(TypedDict, total=False):
    workspace_id: str
    project_id: str
    collection_id: str
    asset_ids: list[str]
    limit: int
    answer: bool


class QueryContext(TypedDict, total=False):
    conversation_id: str
    sql: str


class MemberInput(InputModel):
    subject: str
    role: Role
    workspace_id: str | None = None


class MemberUpdate(InputModel):
    role: Role | None = None
    active: bool | None = None


class CatalogCreate(InputModel):
    kind: str
    name: str
    parent_id: str | None = None
    description: str = ""
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class CatalogUpdate(InputModel):
    name: str | None = None
    description: str | None = None
    metadata: dict[str, JsonValue] | None = None


class SearchRequest(InputModel):
    question: str
    workspace_id: str | None = None
    project_id: str | None = None
    collection_id: str | None = None
    asset_ids: list[str] | None = None
    limit: int = 10
    answer: bool = False


class QueryRequest(InputModel):
    dataset_id: str
    question: str = ""
    conversation_id: str | None = None
    sql: str | None = None


class ThreadInput(InputModel):
    folder_id: str | None = None
    title: str = "New conversation"
    scope: KnowledgeScope | None = None


class ThreadFilter(PageFilter, total=False):
    folder_id: str
    unfiled: bool
    project_id: str
    workspace_id: str
    status: Literal["active", "archived", "all"]


class FolderFilter(PageFilter, total=False):
    root_only: bool
    parent_id: str
    workspace_id: str


class FolderCreate(InputModel):
    name: str = Field(min_length=1, max_length=120)
    parent_id: str | None = None
    scope: KnowledgeScope | None = None


class FolderPatch(InputModel):
    expected_revision: int = Field(ge=1, strict=True)
    name: str | None = None
    parent_id: str | None = None


class ThreadPatch(InputModel):
    expected_revision: int = Field(ge=1, strict=True)
    title: str | None = None
    folder_id: str | None = None
    archived: bool | None = None


class TitleRequest(InputModel):
    agent_id: str
    expected_revision: int = Field(ge=1, strict=True)


class TitleSuggestion(ResponseModel):
    title: str
    based_on_revision: int


class DocumentReingestInput(InputModel):
    acknowledge_chunk_invalidation: bool = False


class TableReingestInput(InputModel):
    pass


class ContentEffects(ResponseModel):
    unchanged: bool | None = None
    affected_asset_ids: list[str] = Field(default_factory=list)
    snapshot_id: str | None = None
    file_id: str | None = None
    historical_snapshots_preserved: bool | None = None
    citation_rows_preserved: bool | None = None
    previous_chunk_ids_invalidated: bool | None = None


class Deleted(ResponseModel):
    deleted: bool


class ContentUpdate(ResponseModel):
    asset: CatalogEntry
    source: CatalogEntry | None = None
    table: CatalogEntry | None = None
    version: CatalogEntry
    effects: ContentEffects


class KnowledgeConnectionInput(InputModel):
    domain: Literal["documents", "structured"]
    role: str
    workspace_id: str | None = None
    mode: Literal["provider", "current_agent"] = "provider"
    provider_id: str | None = None
    model_id: str | None = None
    model_options: ModelParameters = Field(default_factory=ModelParameters)
    dimensions: int | None = None
    storage_dimensions: int | None = None
    space_id: str | None = None
    enabled: bool = True
    expected_revision: int | None = None


class KnowledgeConnection(ResponseModel):
    id: str
    tenant_id: str
    workspace_id: str | None = None
    domain: Literal["documents", "structured"]
    role: str
    mode: Literal["provider", "current_agent"]
    provider_id: str | None = None
    model_id: str | None = None
    model_options: dict[str, JsonValue]
    dimensions: int | None = None
    storage_dimensions: int | None = None
    space_id: str | None = None
    embedding_fingerprint: str | None = None
    enabled: bool
    revision: int
    created_by: str
    updated_by: str
    created_at: str
    updated_at: str


class KnowledgeRole(ResponseModel):
    id: str
    domain: Literal["documents", "structured"]
    label: str
    kind: Literal["embedding", "generative"]
    purposes: list[str]
    supports_current_agent: bool
    compatible_index_required: bool
    assignment: Literal["tenant", "workspace"] | None = None
    status: Literal["needs_setup", "assigned", "disabled"]
    runtime_qualification: Literal["not_run"]


class KnowledgeProvider(ResponseModel):
    id: str
    name: str
    kind: Literal["ollama", "openai", "anthropic"]
    api: Literal["chat", "responses", "messages"] | None = None
    model_ids: list[str]
    enabled: bool


class KnowledgeRoles(ResponseModel):
    roles: list[KnowledgeRole]
    model_options_schema: dict[str, JsonValue] = Field(default_factory=dict)
    providers: list[KnowledgeProvider] | None = None


@dataclass(frozen=True)
class BinaryDownload:
    content: bytes
    content_type: str | None
    etag: str | None
    filename: str | None
    not_modified: bool = False
