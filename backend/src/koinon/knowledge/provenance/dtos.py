# Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc.
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import AwareDatetime, Field, JsonValue, model_validator

from koinon.evidence.dtos import Frozen, Identifier, Revision


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
    parameters: dict[str, JsonValue] = Field(default_factory=dict, max_length=64)
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

    @model_validator(mode="after")
    def recorded_binding(self):
        if self.status == "recorded":
            if (
                any(
                    value is None
                    for value in (
                        self.artifact,
                        self.run_id,
                        self.operation,
                        self.parquet_sha256,
                        self.parquet_byte_size,
                        self.row_count,
                        self.actor,
                        self.recorded_at,
                    )
                )
                or not self.steps
            ):
                raise ValueError("Recorded provenance requires its committed artifact and transform binding")
            if tuple(step.ordinal for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
                raise ValueError("Recorded transform steps must be complete and ordered")
            if len({step.id for step in self.steps}) != len(self.steps):
                raise ValueError("Recorded transform steps must have distinct identities")
        elif self.artifact is not None or self.run_id is not None or self.steps:
            raise ValueError("Unrecorded lineage cannot claim an artifact or transform binding")
        return self


class TableSnapshotPage(Frozen):
    items: tuple[TableSnapshotSummary, ...] = Field(max_length=100)
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    pages: int = Field(ge=0)
    has_next: bool
    has_previous: bool
    current_snapshot_id: Identifier | None
