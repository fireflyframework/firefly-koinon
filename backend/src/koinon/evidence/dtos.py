# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

Identifier = Annotated[str, Field(min_length=1, max_length=64)]
Revision = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Presentation(Frozen):
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

    @model_validator(mode="after")
    def immutable_knowledge_identity(self):
        parts = (self.source_version_id, self.extraction_id, self.source_part_id, self.source_part_sha256)
        if any(value is not None for value in parts):
            if (
                self.kind != "document"
                or any(value is None for value in parts)
                or self.chunk_id is not None
                or self.page is not None
                or self.page_basis != "recorded_loader"
                or self.used_revision != "source-part-sha256:" + (self.source_part_sha256 or "")
            ):
                raise ValueError(
                    "Document part provenance requires its exact immutable version/extraction/part tuple"
                )
        elif (
            self.recorded_page is not None
            or self.page_basis is not None
            or (self.used_revision or "").startswith("source-part-sha256:")
        ):
            raise ValueError("Recorded document part coordinates require their immutable binding")
        if self.kind == "knowledge_version":
            prefix = "knowledge-content-sha256:"
            raw = (self.used_revision or "").removeprefix(prefix)
            if (
                self.knowledge_item_id != self.asset_id
                or not self.knowledge_version_id
                or self.knowledge_version is None
                or not (self.used_revision or "").startswith(prefix)
                or len(raw) != 64
                or any(char not in "0123456789abcdef" for char in raw)
                or self.source_id is not None
                or self.snapshot_id is not None
                or self.query_id is not None
            ):
                raise ValueError("A knowledge source requires its exact immutable version/content identity")
        elif any(
            value is not None
            for value in (self.knowledge_item_id, self.knowledge_version_id, self.knowledge_version)
        ):
            raise ValueError("Knowledge identity fields cannot describe a document or dataset")
        return self


class EvidenceManifest(Frozen):
    revision: Revision
    sources: tuple[SourceReference, ...] = Field(default=(), max_length=500)
    complete: bool = False
    omissions: tuple[str, ...] = Field(default=(), max_length=100)


class ConversationMessage(Frozen):
    id: Identifier
    role: Literal["user", "assistant"]
    text: str = Field(max_length=1_000_000)
    status: Literal["completed", "failed", "cancelled"]
    revision: Revision
    private_derived: bool = False
    source_ids: tuple[Identifier, ...] = Field(default=(), max_length=500)
    result_ids: tuple[Identifier, ...] = Field(default=(), max_length=100)
    created_at: AwareDatetime | None = None
    presentation: Presentation | None = None


class ConversationIdentity(Frozen):
    product_name: str = Field(min_length=1, max_length=64, strict=True)
    assistant_name: str = Field(min_length=1, max_length=64, strict=True)
    branding_revision: int = Field(ge=0, le=2147483647, strict=True)
    branding_origin: Literal["deployment", "organization"]
    branding_sha256: Revision

    @field_validator("product_name", "assistant_name")
    @classmethod
    def printable_name(cls, value: str) -> str:
        if not value.isprintable() or not value.strip():
            raise ValueError("Names must contain printable text")
        return value


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
    identity: ConversationIdentity | None = Field(default=None, description=(
        "Presentation identity recorded when the export or share review was created. "
        "Null means historical identity was not recorded; it never uses today's branding."
    ))


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

    @model_validator(mode="after")
    def observed_completeness(self):
        if self.completeness == "bounded" and (self.row_cap is None or self.truncated is None):
            raise ValueError(
                "Historical cap and truncation must be observed before claiming bounded completeness"
            )
        if self.row_cap is not None and self.row_count > self.row_cap:
            raise ValueError("Stored rows exceed the recorded execution cap")
        return self
