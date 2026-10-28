# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
from typing import Literal

from flyquery.core.services.ingestion.coordinates import ColumnOrigin, RowRange


@dataclass(frozen=True, slots=True)
class CellPosition:
    row: int
    column: int

    def __post_init__(self):
        if any(type(value) is not int or value < 0 for value in (self.row, self.column)):
            raise ValueError("Cell positions are zero-based nonnegative integers")


@dataclass(frozen=True, slots=True)
class CoordinateManifest:
    tenant_id: str
    workspace_id: str
    dataset_id: str
    table_id: str
    snapshot_id: str
    status: Literal["complete", "partial", "not_recorded"]
    row_count: int | None = None
    column_count: int | None = None
    index_base: int = 0
    artifact_id: str | None = None
    run_id: str | None = None
    input_sha256: str | None = None
    mapping_sha256: str | None = None
    source_format: str | None = None
    source_variant: str | None = None
    row_kind: str | None = None
    source_sheet: str | None = None
    source_path: tuple[str | int, ...] = ()
    parser_decisions: tuple = ()
    dependencies: tuple = ()
    reason_code: str | None = None
    rejected_source_rows: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class SourceCell:
    output_row: int
    output_column: int
    source_row: int | None
    source_column: int | None
    source_path: tuple[str | int, ...]
    header_cells: tuple[tuple[int, int], ...]
    source_type: str | None


@dataclass(frozen=True, slots=True)
class CoordinateSelection:
    manifest: CoordinateManifest
    items: tuple[SourceCell, ...]


@dataclass(frozen=True, slots=True)
class CoordinatePage[T]:
    manifest: CoordinateManifest
    items: tuple[T, ...]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_previous: bool


RowRangePage = CoordinatePage[RowRange]
ColumnBindingPage = CoordinatePage[ColumnOrigin]
