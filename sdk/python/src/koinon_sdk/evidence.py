# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/evidence/dtos.py
SHA256: 879a5edfc94c73bf0405b557ee624e4f15eb66a51bd7e0911069173bf57de866

Server authorization and semantic validation remain authoritative.
"""

from typing import Annotated, Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import ResponseModel

Identifier = Annotated[str, Field(min_length=1, max_length=64)]
Revision = Annotated[str, Field(pattern="^[a-f0-9]{64}$")]


class Frozen(ResponseModel):
    pass


class EvidencePresentation(Frozen):
    locale: str = Field(default="en-US", min_length=2, max_length=64)
    time_zone: str = Field(default="UTC", min_length=1, max_length=128)
    response_language: str = Field(default="en", min_length=2, max_length=64)


class SourceReference(Frozen):
    id: Identifier
    asset_id: Identifier
    source_id: Identifier | None = None
    title: str = Field(min_length=1, max_length=255)
    kind: Literal["document", "dataset", "knowledge_version"]
    knowledge_item_id: Identifier | None = None
    knowledge_version_id: Identifier | None = None
    knowledge_version: int | None = Field(default=None, ge=1)
    source_version_id: Identifier | None = None
    extraction_id: Identifier | None = None
    source_part_id: Identifier | None = None
    source_part_sha256: Revision | None = None
    recorded_page: int | None = Field(default=None, ge=1)
    page_basis: Literal["recorded_loader"] | None = None
    used_revision: str | None = Field(default=None, min_length=1, max_length=128)
    snapshot_id: Identifier | None = None
    query_id: Identifier | None = None
    chunk_id: Identifier | None = None
    page: int | None = Field(default=None, ge=1)
    section: str | None = Field(default=None, max_length=512)
    quote: str | None = Field(default=None, max_length=8000)
    current_revision: str | None = Field(default=None, min_length=1, max_length=128)
    availability: Literal["available", "changed", "unverified"] = "unverified"


class EvidenceManifest(Frozen):
    revision: Revision
    sources: tuple[SourceReference, ...] = Field(default=(), max_length=500)
    complete: bool = False
    omissions: tuple[str, ...] = Field(default=(), max_length=100)


class ConversationMessage(Frozen):
    id: Identifier
    role: Literal["user", "assistant"]
    text: str = Field(max_length=1000000)
    status: Literal["completed", "failed", "cancelled"]
    revision: Revision
    private_derived: bool = False
    source_ids: tuple[Identifier, ...] = Field(default=(), max_length=500)
    result_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)
    created_at: AwareDatetime | None = None
    presentation: EvidencePresentation | None = None


class ConversationSnapshot(Frozen):
    thread_id: Identifier
    tenant_id: Identifier
    owner_subject: str = Field(min_length=1, max_length=512, repr=False)
    title: str = Field(min_length=1, max_length=160)
    revision: Revision
    messages: tuple[ConversationMessage, ...] = Field(min_length=1, max_length=200)
    sources: tuple[SourceReference, ...] = Field(default=(), max_length=500)
    source_manifest_complete: bool = False
    originating_token_ids: tuple[Identifier, ...] = Field(default=(), max_length=200, repr=False)


class ResultColumn(Frozen):
    name: str = Field(min_length=1, max_length=512)
    data_type: str = Field(min_length=1, max_length=255)


class StoredResult(Frozen):
    query_id: Identifier
    asset_id: Identifier
    revision: Revision
    row_count: int = Field(ge=0)
    row_cap: int | None = Field(ge=1)
    truncated: bool | None
    completeness: Literal["bounded", "unknown"] = "unknown"
    byte_size: int = Field(ge=0)
    columns: tuple[ResultColumn, ...] = Field(default=(), max_length=2000)
    snapshot_ids: tuple[Identifier, ...] = Field(default=(), max_length=500)
    snapshot_manifest_complete: bool = False
    expires_at: AwareDatetime
