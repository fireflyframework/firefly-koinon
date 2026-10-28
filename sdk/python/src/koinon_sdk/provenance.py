# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/provenance/dtos.py
SHA256: ac95b10b55bacea94fb917462f92f640c2408a9353559c2c90fe7323ca68a1ae

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue

from koinon_sdk.evidence import Frozen, Identifier, Revision


class ProvenanceArtifact(Frozen):
    id: Identifier
    original_filename: str = Field(min_length=1, max_length=255)
    sha256: Revision
    byte_size: int = Field(ge=0)
    file_format: str = Field(min_length=1, max_length=64)
    compression: str = Field(max_length=64)
    actor: str = Field(min_length=1, max_length=512)
    admitted_at: AwareDatetime


class ProvenanceTransformStep(Frozen):
    id: Identifier
    ordinal: int = Field(ge=1, le=64)
    kind: str = Field(min_length=1, max_length=128)
    implementation: str = Field(min_length=1, max_length=512)
    implementation_sha256: Revision | None = None
    input_sha256: Revision | None = None
    output_sha256: Revision | None = None
    parameters: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue], max_length=64)
    actor: str = Field(min_length=1, max_length=512)
    recorded_at: AwareDatetime


class TableSnapshotSummary(Frozen):
    dataset_id: Identifier
    table_id: Identifier
    native_dataset_id: Identifier
    native_table_id: Identifier
    snapshot_id: Identifier
    status: Literal["recorded", "not_recorded"]
    snapshot_status: Literal["PARTIAL", "READY", "FAILED"]
    level: Literal["file_section"]
    operation: Literal["upload", "replace", "reingest"] | None = None
    predecessor_snapshot_id: Identifier | None = None
    artifact: ProvenanceArtifact | None = None
    sheet_or_json_path: str | None = Field(default=None, max_length=4096)
    table_label: str | None = Field(default=None, max_length=512)
    parquet_sha256: Revision | None = None
    parquet_byte_size: int | None = Field(default=None, ge=0)
    schema_sha256: Revision | None = None
    row_count: int | None = Field(default=None, ge=0)
    actor: str | None = Field(default=None, max_length=512)
    recorded_at: AwareDatetime | None = None


class TableProvenance(TableSnapshotSummary):
    run_id: Identifier | None = None
    reader_implementation: str | None = Field(default=None, max_length=512)
    reader_sha256: Revision | None = None
    parser_parameters: dict[str, JsonValue] | None = None
    steps: tuple[ProvenanceTransformStep, ...] = Field(default=(), max_length=64)


class TableSnapshotPage(Frozen):
    items: tuple[TableSnapshotSummary, ...] = Field(max_length=100)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool
    current_snapshot_id: Identifier | None
