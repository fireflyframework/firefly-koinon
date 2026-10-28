# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/assistants/audit_dtos.py
SHA256: 3e42b51eededc8abbd11c5502368d759ddc82b0db7f106636bff9d0de2b3ae7c

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import ResponseModel
from koinon_sdk.evidence import SourceReference


class AuditValue(ResponseModel):
    pass


class GenerationReceipt(AuditValue):
    id: str = Field(min_length=1, max_length=64)
    start_sequence: int = Field(ge=0)
    agent_id: str = Field(min_length=1, max_length=64)
    agent_revision: int = Field(ge=1)
    provider_id: str = Field(min_length=1, max_length=64)
    provider_revision: int = Field(ge=1)
    provider_kind: Literal["ollama", "openai", "anthropic"]
    model_id: str = Field(min_length=1, max_length=255)
    model_class: str = Field(min_length=1, max_length=128)
    api: Literal["chat", "responses", "messages"]
    started_at: AwareDatetime
    finished_at: AwareDatetime | None = None
    status: Literal["started", "completed", "failed"] = "started"


class NativeReadOrigin(AuditValue):
    original_filename: str | None = Field(default=None, max_length=512)
    sheet_or_json_path: str | None = Field(default=None, max_length=1024)
    connection_id: str | None = Field(default=None, max_length=255)
    connection_name: str | None = Field(default=None, max_length=255)
    database: str | None = Field(default=None, max_length=255)
    schema_name: str | None = Field(default=None, alias="schema", max_length=255)
    table: str | None = Field(default=None, max_length=512)


class NativeTableSnapshot(AuditValue):
    table_id: str = Field(min_length=1, max_length=64)
    table_name: str = Field(min_length=1, max_length=512)
    snapshot_id: str = Field(min_length=1, max_length=64)


class NativeReadReceipt(AuditValue):
    result_id: str = Field(min_length=1, max_length=64)
    generation_id: str | None = None
    stage: str = Field(min_length=1, max_length=64)
    domain: Literal["documents", "structured", "knowledge"]
    tenant_id: str = Field(min_length=1, max_length=64)
    workspace_id: str = Field(min_length=1, max_length=64)
    entity_id: str = Field(min_length=1, max_length=64)
    content_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    source_ids: list[str] = Field(default_factory=list[str], max_length=500)
    snapshot_ids: list[str] = Field(default_factory=list[str], max_length=500)
    engine: str | None = Field(default=None, max_length=64)
    database: str | None = Field(default=None, max_length=255)
    catalog: str | None = Field(default=None, max_length=255)
    schema_name: str | None = Field(default=None, alias="schema", max_length=255)
    read_kind: Literal["indexed_document", "metadata", "document_extraction", "knowledge_version"] | None = (
        None
    )
    origin: NativeReadOrigin | None = None
    source_version_id: str | None = Field(default=None, min_length=1, max_length=64)
    extraction_id: str | None = Field(default=None, min_length=1, max_length=64)
    knowledge_item_id: str | None = Field(default=None, min_length=1, max_length=64)
    knowledge_version_id: str | None = Field(default=None, min_length=1, max_length=64)
    knowledge_version: int | None = Field(default=None, ge=1)


class SqlAttemptReceipt(AuditValue):
    result_id: str = Field(min_length=1, max_length=64)
    generation_id: str | None = None
    ordinal: int = Field(ge=1, le=1000)
    stage: str = Field(min_length=1, max_length=64)
    statement_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    statement: str | None = Field(default=None, max_length=32768)
    classification: str | None = Field(default=None, max_length=64)
    outcome: str = Field(min_length=1, max_length=64)
    executed: bool
    snapshot_pins: dict[str, str] = Field(default_factory=dict[str, str], max_length=500)
    row_count: int | None = Field(default=None, ge=0)
    truncated: bool | None = None
    reason_code: str | None = Field(default=None, max_length=64)
    engine: str | None = Field(default=None, max_length=64)
    database: str | None = Field(default=None, max_length=255)
    catalog: str | None = Field(default=None, max_length=255)
    schema_name: str | None = Field(default=None, alias="schema", max_length=255)
    execution_kind: Literal["imported_snapshot", "computed"] | None = None
    dataset_id: str | None = Field(default=None, max_length=64)
    native_dataset_id: str | None = Field(default=None, max_length=64)
    tables: list[NativeTableSnapshot] = Field(default_factory=list[NativeTableSnapshot], max_length=500)


class PrivateFileReceipt(AuditValue):
    id: str = Field(min_length=1, max_length=64)
    filename: str = Field(min_length=1, max_length=512)
    media_type: str = Field(min_length=1, max_length=255)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")
    used_revision: int = Field(ge=1)
    availability: Literal["available", "expired", "deleted", "changed", "unavailable"]


class AnswerAudit(AuditValue):
    run_id: str
    provenance_status: Literal["recorded", "not_recorded"]
    source_provenance_complete: bool | None = None
    generations: list[GenerationReceipt] = Field(default_factory=list[GenerationReceipt], max_length=100)
    sources: list[SourceReference] = Field(default_factory=list[SourceReference], max_length=500)
    private_files: list[PrivateFileReceipt] = Field(default_factory=list[PrivateFileReceipt], max_length=10)
    native_reads: list[NativeReadReceipt] = Field(default_factory=list[NativeReadReceipt], max_length=1000)
    sql_attempts: list[SqlAttemptReceipt] = Field(default_factory=list[SqlAttemptReceipt], max_length=1000)
