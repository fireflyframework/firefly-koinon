# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-observed source positions; every internal row/field index is zero-based."""

import json
from dataclasses import asdict, dataclass
from hashlib import file_digest, sha256
from typing import Literal

Scalar = str | int | float | bool | None


def input_digest(path: str) -> str:
    with open(path, "rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


@dataclass(frozen=True, slots=True)
class RowRange:
    output_start: int
    count: int
    source_start: int
    source_stride: int = 1

    def __post_init__(self):
        if (
            any(
                type(n) is not int
                for n in (self.output_start, self.count, self.source_start, self.source_stride)
            )
            or self.output_start < 0
            or self.source_start < 0
            or self.count <= 0
            or self.source_stride <= 0
        ):
            raise ValueError("Invalid reader-observed row range")


@dataclass(frozen=True, slots=True)
class ColumnOrigin:
    output_position: int
    source_field_index: int | None
    source_path: tuple[str | int, ...] = ()
    source_type: str | None = None
    header_cells: tuple[tuple[int, int], ...] = ()

    def __post_init__(self):
        if (
            type(self.output_position) is not int
            or self.output_position < 0
            or self.source_field_index is not None
            and (type(self.source_field_index) is not int or self.source_field_index < 0)
        ):
            raise ValueError("Invalid source column index")
        if any(type(part) not in (str, int) or type(part) is int and part < 0 for part in self.source_path):
            raise ValueError("Invalid observed source field path")
        if any(
            len(cell) != 2 or any(type(value) is not int or value < 0 for value in cell)
            for cell in self.header_cells
        ):
            raise ValueError("Invalid observed header coordinate")


@dataclass(frozen=True, slots=True)
class MaterializationCoordinates:
    source_format: str
    source_variant: str
    row_kind: Literal["record", "sheet_row", "json_array", "jsonl_record", "single_object"]
    input_sha256: str
    row_count: int
    column_count: int
    row_ranges: tuple[RowRange, ...]
    columns: tuple[ColumnOrigin, ...]
    parser_decisions: tuple[tuple[str, Scalar], ...] = ()
    dependencies: tuple[tuple[str, str | None], ...] = ()
    source_sheet: str | None = None
    source_path: tuple[str | int, ...] = ()
    complete: bool = True
    reason_code: str | None = None
    version: int = 1
    index_base: int = 0
    rejected_source_rows: tuple[int, ...] = ()

    def __post_init__(self):
        if (
            type(self.index_base) is not int
            or self.index_base != 0
            or type(self.version) is not int
            or self.version != 1
            or len(self.input_sha256) != 64
            or any(c not in "0123456789abcdef" for c in self.input_sha256)
        ):
            raise ValueError("Invalid source coordinate version or digest")
        if any(type(n) is not int or n < 0 for n in (self.row_count, self.column_count)):
            raise ValueError("Invalid coordinate output counts")
        if any(type(row) is not int or row < 0 for row in self.rejected_source_rows) or len(
            set(self.rejected_source_rows)
        ) != len(self.rejected_source_rows):
            raise ValueError("Invalid rejected source positions")
        end = 0
        for span in self.row_ranges:
            if (
                span.output_start < end
                or span.output_start + span.count > self.row_count
                or self.complete
                and span.output_start != end
            ):
                raise ValueError("Reader row ranges do not cover the actual output")
            end = span.output_start + span.count
        if self.complete and end != self.row_count:
            raise ValueError("Reader row ranges do not cover the actual output")
        positions = [column.output_position for column in self.columns]
        if (
            len(set(positions)) != len(positions)
            or any(p >= self.column_count for p in positions)
            or self.complete
            and set(positions) != set(range(self.column_count))
        ):
            raise ValueError("Reader column origins do not cover the actual output columns")
        if self.complete and self.reason_code is not None or not self.complete and not self.reason_code:
            raise ValueError("Incomplete coordinate mappings require an explicit reason")

    def digest(self) -> str:
        return sha256(
            json.dumps(
                asdict(self), sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")
            ).encode()
        ).hexdigest()


def record_coordinates(
    source_path,
    source_format,
    source_variant,
    schema,
    row_count,
    *,
    dependencies=(),
    source_fields=None,
    source_types=None,
):
    fields = list(schema)
    origins = tuple(
        ColumnOrigin(
            i,
            i if source_fields is None else source_fields.get(field.name),
            (field.name,),
            str(field.type) if source_types is None else source_types.get(field.name),
        )
        for i, field in enumerate(fields)
    )
    known = all(column.source_field_index is not None for column in origins)
    return MaterializationCoordinates(
        source_format,
        source_variant,
        "record",
        input_digest(source_path),
        row_count,
        len(fields),
        (RowRange(0, row_count, 0),) if row_count else (),
        origins,
        parser_decisions=(("row_order", "source_record_order"),),
        dependencies=tuple(dependencies),
        complete=known,
        reason_code=None if known else "UNRECORDED_SOURCE_FIELDS",
    )
