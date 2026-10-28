# Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc.
# SPDX-License-Identifier: Apache-2.0
"""Public, value-free coordinates for one immutable table snapshot."""

from typing import Annotated, Literal

from pydantic import Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from koinon.evidence.dtos import Frozen, Identifier, Revision

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

    @model_validator(mode="after")
    def distinct_cells(self):
        if len({(cell.row, cell.column) for cell in self.cells}) != len(self.cells):
            raise ValueError("Select distinct zero-based cells")
        return self


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

    @model_validator(mode="after")
    def observed_mapping(self):
        required = (
            self.row_count,
            self.column_count,
            self.artifact_id,
            self.run_id,
            self.input_sha256,
            self.mapping_sha256,
            self.source_format,
            self.source_variant,
            self.row_kind,
        )
        if self.status == "not_recorded":
            if any(value is not None for value in (*required, self.source_sheet, self.reason_code)) or any(
                (
                    self.source_path,
                    self.parser_decisions,
                    self.dependencies,
                    self.rejected_source_rows,
                )
            ):
                raise ValueError("Unrecorded coordinates cannot claim an observed source mapping")
        elif any(value is None for value in required):
            raise ValueError("Recorded coordinates require their exact input and mapping identity")
        elif (self.status == "partial") != (self.reason_code is not None):
            raise ValueError("Partial mappings require an explicit reason")
        for pairs in (self.parser_decisions, self.dependencies):
            if len({pair.name for pair in pairs}) != len(pairs):
                raise ValueError("Recorded parameter and dependency names must be distinct")
        if len(set(self.rejected_source_rows)) != len(self.rejected_source_rows):
            raise ValueError("Rejected source positions must be distinct")
        return self


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
