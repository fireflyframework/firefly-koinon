# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/knowledge/provenance/coordinate_dtos.py
SHA256: bd7050f2b37ce5a8c2ce0411c1707f7109cc28372e177ab3a1a919f0e78ada8f

Server authorization and semantic validation remain authoritative.
"""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr

from koinon_sdk.evidence import Frozen, Identifier, Revision

Position = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]
PathPart = Annotated[str, Field(strict=True, max_length=4096)] | Position
SourcePath = Annotated[tuple[PathPart, ...], Field(max_length=64)]
Label = Annotated[str, Field(strict=True, min_length=1, max_length=512)]
SourceType = Annotated[str, Field(strict=True, min_length=1, max_length=4096)]
Scalar = StrictStr | StrictInt | Annotated[StrictFloat, Field(allow_inf_nan=False)] | StrictBool | None


class CoordinateCellPosition(Frozen):
    row: Position
    column: Position


class CoordinateHeaderCell(Frozen):
    row: Position
    column: Position


HeaderCells = Annotated[tuple[CoordinateHeaderCell, ...], Field(max_length=1024)]


class CoordinateParserDecision(Frozen):
    name: Label
    value: Scalar


class CoordinateDependency(Frozen):
    name: Label
    version: Label | None


class CoordinateCellRequest(Frozen):
    snapshot_id: Identifier
    cells: tuple[CoordinateCellPosition, ...] = Field(min_length=1, max_length=1000)


class TableCoordinateManifest(Frozen):
    dataset_id: Identifier
    table_id: Identifier
    native_dataset_id: Identifier
    native_table_id: Identifier
    snapshot_id: Identifier
    status: Literal["complete", "partial", "not_recorded"]
    index_base: Annotated[int, Field(strict=True, ge=0, le=0)] = 0
    row_count: Position | None = None
    column_count: Position | None = None
    artifact_id: Identifier | None = None
    run_id: Identifier | None = None
    input_sha256: Revision | None = None
    mapping_sha256: Revision | None = None
    source_format: Label | None = None
    source_variant: Label | None = None
    row_kind: Literal["record", "sheet_row", "json_array", "jsonl_record", "single_object"] | None = None
    source_sheet: Label | None = None
    source_path: SourcePath = ()
    parser_decisions: tuple[CoordinateParserDecision, ...] = Field(default=(), max_length=128)
    dependencies: tuple[CoordinateDependency, ...] = Field(default=(), max_length=128)
    reason_code: Label | None = None
    rejected_source_rows: tuple[Position, ...] = Field(default=(), max_length=1024)


class CoordinateSourceCell(Frozen):
    output_row: Position
    output_column: Position
    source_row: Position | None
    source_column: Position | None
    source_path: SourcePath
    header_cells: HeaderCells
    source_type: SourceType | None


class TableCoordinateSelection(Frozen):
    manifest: TableCoordinateManifest
    items: tuple[CoordinateSourceCell, ...] = Field(max_length=1000)


class CoordinateRowRange(Frozen):
    output_start: Position
    count: Annotated[int, Field(strict=True, ge=1, le=9007199254740991)]
    source_start: Position
    source_stride: Annotated[int, Field(strict=True, ge=1, le=9007199254740991)]


class CoordinateColumnBinding(Frozen):
    output_position: Position
    source_field_index: Position | None
    source_path: SourcePath
    source_type: SourceType | None
    header_cells: HeaderCells


class CoordinatePage(Frozen):
    manifest: TableCoordinateManifest
    total: Position
    page: Annotated[int, Field(strict=True, ge=1)]
    page_size: Annotated[int, Field(strict=True, ge=1, le=100)]
    pages: Position
    has_next: StrictBool
    has_previous: StrictBool


class TableRowRangePage(CoordinatePage):
    items: tuple[CoordinateRowRange, ...] = Field(max_length=100)


class TableColumnBindingPage(CoordinatePage):
    items: tuple[CoordinateColumnBinding, ...] = Field(max_length=100)
