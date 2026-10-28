# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass

from koinon.evidence.dtos import SourceReference


@dataclass(frozen=True, slots=True)
class CapturedEvidence:
    data: dict
    sources: tuple[SourceReference, ...]
    complete: bool
    native_reads: tuple["NativeReadFingerprint", ...] = ()
    sql_attempts: tuple["NativeSqlAttempt", ...] = ()


@dataclass(frozen=True, slots=True)
class DocumentRead:
    workspace_id: str
    source_id: str
    chunk_id: str
    digest: str
    quote: str
    page: int | None
    section: str | None
    source_version_id: str | None = None
    extraction_id: str | None = None
    source_part_id: str | None = None
    source_part_sha256: str | None = None
    recorded_page: int | None = None


@dataclass(frozen=True, slots=True)
class DocumentExtractionRead:
    workspace_id: str
    source_id: str
    source_version_id: str
    extraction_id: str


@dataclass(frozen=True, slots=True)
class SnapshotRead:
    workspace_id: str
    dataset_id: str
    table_id: str | None
    table_name: str | None
    snapshot_id: str
    query_id: str | None


@dataclass(frozen=True, slots=True)
class NativeReadOrigin:
    original_filename: str | None = None
    sheet_or_json_path: str | None = None
    connection_id: str | None = None
    connection_name: str | None = None
    database: str | None = None
    schema: str | None = None
    table: str | None = None


@dataclass(frozen=True, slots=True)
class NativeDatabaseContext:
    engine: str | None = None
    database: str | None = None
    catalog: str | None = None
    schema: str | None = None


@dataclass(frozen=True, slots=True)
class NativeTableSnapshot:
    table_id: str
    table_name: str
    snapshot_id: str


@dataclass(frozen=True, slots=True)
class NativeReadFingerprint:
    stage: str
    domain: str
    tenant_id: str
    workspace_id: str
    entity_id: str
    content_sha256: str
    source_ids: tuple[str, ...]
    snapshot_ids: tuple[str, ...]
    engine: str | None = None
    database: str | None = None
    catalog: str | None = None
    schema: str | None = None
    read_kind: str | None = None
    origin: NativeReadOrigin | None = None
    source_version_id: str | None = None
    extraction_id: str | None = None
    knowledge_item_id: str | None = None
    knowledge_version_id: str | None = None
    knowledge_version: int | None = None


@dataclass(frozen=True, slots=True)
class NativeSqlAttempt:
    ordinal: int
    stage: str
    statement_sha256: str
    classification: str | None
    outcome: str
    executed: bool
    snapshot_pins: dict[str, str]
    row_count: int | None = None
    truncated: bool | None = None
    reason_code: str | None = None
    statement: str | None = None
    engine: str | None = None
    database: str | None = None
    catalog: str | None = None
    schema: str | None = None
    execution_kind: str | None = None
    dataset_id: str | None = None
    native_dataset_id: str | None = None
    tables: tuple[NativeTableSnapshot, ...] = ()


@dataclass(frozen=True, slots=True)
class NativeCaptureLimits:
    """Private remaining allowances supplied by the current-generation consumer."""

    reads: int = 512
    attempts: int = 128
    sources: int = 500
    receipt_bytes: int = 524288
    ids_per_read: int = 500

    def __post_init__(self):
        for name, maximum in (
            ("reads", 1000),
            ("attempts", 1000),
            ("sources", 500),
            ("receipt_bytes", 524288),
            ("ids_per_read", 500),
        ):
            value = getattr(self, name)
            if type(value) is not int or not (1 if name == "ids_per_read" else 0) <= value <= maximum:
                raise ValueError("Native capture allowances must be bounded nonnegative integers")
