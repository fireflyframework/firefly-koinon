# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from contextlib import asynccontextmanager
from dataclasses import asdict
from uuid import UUID

from flyquery.core.services.ingestion.coordinates import ColumnOrigin, MaterializationCoordinates, RowRange
from flyquery.core.services.ingestion.lineage import LineageError
from flyquery.models.entities.schema import SchemaSnapshot
from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import InvalidRequestException
from sqlalchemy import and_, or_, select

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.lineage.coordinate_dtos import (
    CoordinateManifest,
    CoordinatePage,
    CoordinateSelection,
    SourceCell,
)
from koinon.knowledge.lineage.coordinate_entities import (
    CoordinateColumnRow,
    CoordinateManifestRow,
    CoordinateRangeRow,
)
from koinon.knowledge.lineage.coordinate_ports import StructuredCoordinatesPort
from koinon.knowledge.lineage.coordinate_repositories import CoordinateRepository, filters


def unavailable():
    return AccessDenied(
        "Snapshot input coordinates are unavailable in this scope", code="PROVENANCE_UNAVAILABLE"
    )


async def persist_coordinates(
    session,
    *,
    actor,
    tenant_id,
    workspace_id,
    dataset_id,
    table_id,
    snapshot_id,
    run_id,
    artifact_id,
    coordinates,
    row_count,
    column_count,
    input_sha256,
):
    """Join snapshot binding; a mapping failure rolls back that same native transaction."""
    if not isinstance(coordinates, MaterializationCoordinates):
        raise LineageError("A typed reader coordinate receipt is required")
    if (coordinates.row_count, coordinates.column_count, coordinates.input_sha256) != (
        row_count,
        column_count,
        input_sha256,
    ):
        raise LineageError("Reader coordinates differ from the verified materialization")
    if (
        len(coordinates.row_ranges) > 100000
        or len(coordinates.columns) > 16384
        or len(coordinates.rejected_source_rows) > 1024
    ):
        raise LineageError("Reader coordinates exceed the explicit mapping budget")
    descriptor = asdict(coordinates)
    if len(json.dumps(descriptor, ensure_ascii=False).encode()) > 8388608:
        raise LineageError("Reader coordinates exceed the explicit mapping budget")
    descriptor.pop("row_ranges")
    descriptor.pop("columns")
    scope = dict(
        actor=actor,
        tenant_id=tenant_id,
        workspace_id=UUID(str(workspace_id)),
        dataset_id=UUID(str(dataset_id)),
        snapshot_id=UUID(str(snapshot_id)),
    )
    session.add(
        CoordinateManifestRow(
            **scope,
            table_id=UUID(str(table_id)),
            run_id=UUID(str(run_id)),
            artifact_id=UUID(str(artifact_id)),
            input_sha256=coordinates.input_sha256,
            mapping_sha256=coordinates.digest(),
            row_count=row_count,
            column_count=column_count,
            complete=coordinates.complete,
            reason_code=coordinates.reason_code,
            descriptor=descriptor,
        )
    )
    await session.flush()
    session.add_all([CoordinateRangeRow(**scope, **asdict(row)) for row in coordinates.row_ranges])
    session.add_all([CoordinateColumnRow(**scope, **asdict(column)) for column in coordinates.columns])
    await session.flush()


def row_dto(row):
    return RowRange(row.output_start, row.count, row.source_start, row.source_stride)


def column_dto(row):
    return ColumnOrigin(
        row.output_position,
        row.source_field_index,
        tuple(row.source_path),
        row.source_type,
        tuple(tuple(cell) for cell in row.header_cells),
    )


@service(name="knowledge.structured_coordinates")
class NativeStructuredCoordinates(StructuredCoordinatesPort):
    def __init__(self, datasources: DataSourceRegistry):
        self.datasources = datasources

    @asynccontextmanager
    async def _read(self, values):
        from koinon.knowledge.adapters import native_scope

        scope = dict(
            tenant_id=values["tenant_id"],
            workspace_id=UUID(values["workspace_id"]),
            dataset_id=UUID(values["dataset_id"]),
            snapshot_id=UUID(values["snapshot_id"]),
        )
        with native_scope("structured", values["tenant_id"], values["workspace_id"], values["actor"]):
            async with infrastructure_unit(self.datasources.get("structured"), read_only=True) as session:
                actual = (
                    await session.execute(
                        select(
                            SchemaSnapshot.id, SchemaSnapshot.n_rows_actual, SchemaSnapshot.n_columns
                        ).where(
                            SchemaSnapshot.id == scope["snapshot_id"],
                            SchemaSnapshot.tenant_id == scope["tenant_id"],
                            SchemaSnapshot.workspace_id == scope["workspace_id"],
                            SchemaSnapshot.dataset_id == scope["dataset_id"],
                            SchemaSnapshot.table_id == UUID(values["table_id"]),
                        )
                    )
                ).one_or_none()
                if actual is None:
                    raise unavailable()
                manifest = await CoordinateRepository.one(session, CoordinateManifestRow, scope)
                common = {
                    key: values[key]
                    for key in ("tenant_id", "workspace_id", "dataset_id", "table_id", "snapshot_id")
                }
                if manifest is None:
                    dto = CoordinateManifest(**common, status="not_recorded")
                else:
                    if (
                        manifest.table_id != UUID(values["table_id"])
                        or manifest.row_count != actual.n_rows_actual
                        or manifest.column_count != actual.n_columns
                    ):
                        raise unavailable()
                    data = manifest.descriptor
                    dto = CoordinateManifest(
                        **common,
                        status="complete" if manifest.complete else "partial",
                        row_count=manifest.row_count,
                        column_count=manifest.column_count,
                        artifact_id=str(manifest.artifact_id),
                        run_id=str(manifest.run_id),
                        input_sha256=manifest.input_sha256,
                        mapping_sha256=manifest.mapping_sha256,
                        source_format=data["source_format"],
                        source_variant=data["source_variant"],
                        row_kind=data["row_kind"],
                        source_sheet=data["source_sheet"],
                        source_path=tuple(data["source_path"]),
                        parser_decisions=tuple(tuple(item) for item in data["parser_decisions"]),
                        dependencies=tuple(tuple(item) for item in data["dependencies"]),
                        reason_code=manifest.reason_code,
                        rejected_source_rows=tuple(data["rejected_source_rows"]),
                    )
                yield session, scope, dto

    async def read_manifest(self, **scope):
        async with self._read(scope) as (_, _, manifest):
            return manifest

    async def read_cells(self, *, cells, **values):
        if not 1 <= len(cells) <= 1000 or len(set(cells)) != len(cells):
            raise InvalidRequestException(
                "Select 1–1000 distinct zero-based cells", code="INVALID_COORDINATES"
            )
        async with self._read(values) as (session, scope, manifest):
            if manifest.status == "not_recorded":
                return CoordinateSelection(manifest, ())
            if any(cell.row >= manifest.row_count or cell.column >= manifest.column_count for cell in cells):
                raise InvalidRequestException(
                    "Selected cell exceeds the exact snapshot bounds", code="INVALID_COORDINATES"
                )
            rows = (
                (
                    await session.execute(
                        select(CoordinateRangeRow).where(
                            *filters(CoordinateRangeRow, scope),
                            or_(
                                *[
                                    and_(
                                        CoordinateRangeRow.output_start <= row,
                                        CoordinateRangeRow.output_start + CoordinateRangeRow.count > row,
                                    )
                                    for row in {cell.row for cell in cells}
                                ]
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            )
            columns = (
                (
                    await session.execute(
                        select(CoordinateColumnRow).where(
                            *filters(CoordinateColumnRow, scope),
                            CoordinateColumnRow.output_position.in_({cell.column for cell in cells}),
                        )
                    )
                )
                .scalars()
                .all()
            )
            indexed = {column.output_position: column for column in columns}
            points = []
            for cell in cells:
                span = next(
                    (row for row in rows if row.output_start <= cell.row < row.output_start + row.count), None
                )
                column = indexed.get(cell.column)
                if manifest.status == "complete" and (span is None or column is None):
                    raise unavailable()
                points.append(
                    SourceCell(
                        cell.row,
                        cell.column,
                        span.source_start + (cell.row - span.output_start) * span.source_stride
                        if span
                        else None,
                        column.source_field_index if column else None,
                        tuple(column.source_path) if column else (),
                        tuple(tuple(point) for point in column.header_cells) if column else (),
                        column.source_type if column else None,
                    )
                )
            return CoordinateSelection(manifest, tuple(points))

    async def _page(self, entity, order, convert, values, page, page_size):
        if type(page) is not int or type(page_size) is not int or page < 1 or not 1 <= page_size <= 100:
            raise InvalidRequestException("Use a positive page and page_size up to100", code="INVALID_PAGE")
        async with self._read(values) as (session, scope, manifest):
            rows, total = await CoordinateRepository.page(session, entity, scope, order, page, page_size)
            return CoordinatePage(
                manifest,
                tuple(map(convert, rows)),
                total,
                page,
                page_size,
                (total + page_size - 1) // page_size,
                page * page_size < total,
                page > 1,
            )

    async def read_row_ranges(self, *, page=1, page_size=25, **scope):
        return await self._page(
            CoordinateRangeRow, CoordinateRangeRow.output_start, row_dto, scope, page, page_size
        )

    async def read_column_bindings(self, *, page=1, page_size=25, **scope):
        return await self._page(
            CoordinateColumnRow, CoordinateColumnRow.output_position, column_dto, scope, page, page_size
        )
