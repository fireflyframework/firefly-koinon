# Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc.
# SPDX-License-Identifier: Apache-2.0
"""Resolve canonical authority before inspecting immutable native coordinates."""

from dataclasses import asdict
from uuid import UUID

from pydantic import ValidationError
from pyfly.container import Provider, service
from pyfly.data.relational.datasource_registry import NoSuchDataSourceError
from pyfly.kernel import InvalidRequestException, ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.lineage.coordinate_dtos import CellPosition, CoordinateManifest
from koinon.knowledge.lineage.coordinate_ports import StructuredCoordinatesPort
from koinon.knowledge.provenance.coordinate_dtos import (
    CoordinateCellRequest,
    TableColumnBindingPage,
    TableCoordinateManifest,
    TableCoordinateSelection,
    TableRowRangePage,
)
from koinon.knowledge.provenance.service import TableProvenanceService


def invalid_record():
    return ServiceUnavailableException(
        "The recorded source coordinates are incomplete. Reload and try again.",
        code="COORDINATE_RECORD_INVALID",
    )


def coordinate_item(row):
    values = asdict(row)
    if "header_cells" in values:
        values["header_cells"] = tuple({"row": r, "column": c} for r, c in values["header_cells"])
    return values


@service
class TableCoordinateService:
    def __init__(
        self, provenance: TableProvenanceService, coordinates: Provider[StructuredCoordinatesPort | None]
    ):
        self.provenance = provenance
        self.coordinates = coordinates

    def _reader(self) -> StructuredCoordinatesPort:
        reader = self.coordinates.get()
        if reader is None:
            raise ServiceUnavailableException(
                "Structured source coordinates are not configured", code="COORDINATES_UNAVAILABLE"
            )
        return reader

    async def _scope(self, subject, tenant_id, dataset_id, table_id, snapshot_id):
        try:
            snapshot_id = str(UUID(snapshot_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise InvalidRequestException("Choose a valid snapshot", code="INVALID_SNAPSHOT") from error
        dataset, table = await self.provenance._bindings(subject, tenant_id, dataset_id, table_id)
        return dict(
            actor=subject,
            tenant_id=tenant_id,
            workspace_id=dataset.native_workspace_id,
            dataset_id=dataset.native_id,
            table_id=table.native_id,
            snapshot_id=snapshot_id,
        )

    @staticmethod
    def _manifest(row: CoordinateManifest, scope, dataset_id, table_id) -> TableCoordinateManifest:
        if any(
            getattr(row, key) != scope[key]
            for key in (
                "tenant_id",
                "workspace_id",
                "dataset_id",
                "table_id",
                "snapshot_id",
            )
        ):
            raise AccessDenied(
                "Source coordinates are unavailable in this scope", code="PROVENANCE_SCOPE_MISMATCH"
            )
        values = asdict(row)
        values.pop("tenant_id")
        values.pop("workspace_id")
        values.update(
            dataset_id=dataset_id,
            table_id=table_id,
            native_dataset_id=row.dataset_id,
            native_table_id=row.table_id,
        )
        try:
            values["parser_decisions"] = tuple(
                {"name": name, "value": value} for name, value in row.parser_decisions
            )
            values["dependencies"] = tuple(
                {"name": name, "version": version} for name, version in row.dependencies
            )
            return TableCoordinateManifest.model_validate(values)
        except (ValueError, TypeError) as error:
            raise invalid_record() from error

    async def _read(self, method, scope, **parameters):
        try:
            return await method(**scope, **parameters)
        except NoSuchDataSourceError:
            raise ServiceUnavailableException(
                "Configure the structured datasource to inspect source coordinates",
                code="COORDINATES_UNAVAILABLE",
            ) from None

    async def manifest(
        self, subject, tenant_id, dataset_id, table_id, snapshot_id
    ) -> TableCoordinateManifest:
        scope = await self._scope(subject, tenant_id, dataset_id, table_id, snapshot_id)
        row = await self._read(self._reader().read_manifest, scope)
        return self._manifest(row, scope, dataset_id, table_id)

    async def cells(
        self, subject, tenant_id, dataset_id, table_id, request: CoordinateCellRequest
    ) -> TableCoordinateSelection:
        scope = await self._scope(subject, tenant_id, dataset_id, table_id, request.snapshot_id)
        result = await self._read(
            self._reader().read_cells,
            scope,
            cells=tuple(CellPosition(cell.row, cell.column) for cell in request.cells),
        )
        manifest = self._manifest(result.manifest, scope, dataset_id, table_id)
        try:
            value = TableCoordinateSelection.model_validate(
                {"manifest": manifest, "items": tuple(coordinate_item(item) for item in result.items)}
            )
        except (ValueError, TypeError) as error:
            raise invalid_record() from error
        if manifest.status == "not_recorded":
            if value.items:
                raise invalid_record()
        elif (
            [(cell.output_row, cell.output_column) for cell in value.items]
            != [(cell.row, cell.column) for cell in request.cells]
            or any(
                cell.output_row >= (manifest.row_count or 0)
                or cell.output_column >= (manifest.column_count or 0)
                for cell in value.items
            )
            or manifest.status == "complete"
            and any(cell.source_row is None for cell in value.items)
        ):
            raise invalid_record()
        return value

    async def _page(self, method, subject, tenant_id, dataset_id, table_id, snapshot_id, page, page_size):
        if (
            type(page) is not int
            or type(page_size) is not int
            or page < 1
            or not 1 <= page_size <= 100
            or (page - 1) * page_size > 1_000_000
        ):
            raise InvalidRequestException("Choose a valid page and page size up to 100", code="INVALID_PAGE")
        scope = await self._scope(subject, tenant_id, dataset_id, table_id, snapshot_id)
        result = await self._read(method(self._reader()), scope, page=page, page_size=page_size)
        manifest = self._manifest(result.manifest, scope, dataset_id, table_id)
        if (
            type(result.total) is not int
            or result.total < 0
            or any(type(value) is not int for value in (result.page, result.page_size, result.total_pages))
            or result.page != page
            or result.page_size != page_size
            or result.total_pages != (result.total + page_size - 1) // page_size
            or type(result.has_next) is not bool
            or type(result.has_previous) is not bool
            or result.has_next != (page * page_size < result.total)
            or result.has_previous != (page > 1)
            or len(result.items) != min(page_size, max(0, result.total - (page - 1) * page_size))
            or manifest.status == "not_recorded"
            and result.total != 0
        ):
            raise invalid_record()
        try:
            items = tuple(coordinate_item(item) for item in result.items)
        except (ValueError, TypeError) as error:
            raise invalid_record() from error
        return dict(
            manifest=manifest,
            items=items,
            total=result.total,
            page=page,
            page_size=page_size,
            pages=result.total_pages,
            has_next=result.has_next,
            has_previous=result.has_previous,
        )

    async def rows(
        self, subject, tenant_id, dataset_id, table_id, snapshot_id, *, page=1, page_size=25
    ) -> TableRowRangePage:
        data = await self._page(
            lambda reader: reader.read_row_ranges,
            subject,
            tenant_id,
            dataset_id,
            table_id,
            snapshot_id,
            page,
            page_size,
        )
        try:
            value = TableRowRangePage.model_validate(data)
        except ValidationError as error:
            raise invalid_record() from error
        end = 0
        for item in value.items:
            if item.output_start < end or item.output_start + item.count > (value.manifest.row_count or 0):
                raise invalid_record()
            end = item.output_start + item.count
        return value

    async def columns(
        self, subject, tenant_id, dataset_id, table_id, snapshot_id, *, page=1, page_size=25
    ) -> TableColumnBindingPage:
        data = await self._page(
            lambda reader: reader.read_column_bindings,
            subject,
            tenant_id,
            dataset_id,
            table_id,
            snapshot_id,
            page,
            page_size,
        )
        try:
            value = TableColumnBindingPage.model_validate(data)
        except ValidationError as error:
            raise invalid_record() from error
        positions = [item.output_position for item in value.items]
        if (
            positions != sorted(set(positions))
            or any(pos >= (value.manifest.column_count or 0) for pos in positions)
            or value.total > (value.manifest.column_count or 0)
            or value.manifest.status == "complete"
            and value.total != value.manifest.column_count
        ):
            raise invalid_record()
        return value
