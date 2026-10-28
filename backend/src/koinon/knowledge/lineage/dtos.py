# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    id: str
    original_filename: str
    sha256: str
    byte_size: int
    file_format: str
    compression: str
    actor: str
    admitted_at: datetime


@dataclass(frozen=True, slots=True)
class TransformStep:
    id: str
    ordinal: int
    kind: str
    implementation: str
    input_sha256: str | None
    output_sha256: str | None
    parameters: dict
    actor: str
    recorded_at: datetime
    implementation_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class SnapshotLineage:
    tenant_id: str
    workspace_id: str
    snapshot_id: str
    dataset_id: str
    table_id: str
    status: Literal["recorded", "not_recorded"]
    snapshot_status: str
    level: Literal["file_section"] = "file_section"
    artifact: SourceArtifact | None = None
    run_id: str | None = None
    operation: str | None = None
    predecessor_snapshot_id: str | None = None
    sheet_or_json_path: str | None = None
    table_label: str | None = None
    parquet_sha256: str | None = None
    parquet_byte_size: int | None = None
    row_count: int | None = None
    actor: str | None = None
    recorded_at: datetime | None = None
    steps: tuple[TransformStep, ...] = ()
    schema_sha256: str | None = None
    reader_implementation: str | None = None
    reader_sha256: str | None = None
    parser_parameters: dict | None = None


@dataclass(frozen=True, slots=True)
class LineagePage:
    items: tuple[SnapshotLineage, ...]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool
    current_snapshot_id: str | None
