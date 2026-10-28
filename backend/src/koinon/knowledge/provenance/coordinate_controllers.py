# Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc.
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.knowledge.provenance.coordinate_dtos import (
    CoordinateCellRequest,
    TableColumnBindingPage,
    TableCoordinateManifest,
    TableCoordinateSelection,
    TableRowRangePage,
)
from koinon.knowledge.provenance.coordinate_service import TableCoordinateService
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.table_coordinates")
@request_mapping("/api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}/coordinates")
class TableCoordinateController:
    def __init__(self, coordinates: TableCoordinateService):
        self.coordinates = coordinates

    @get_mapping("")
    async def manifest(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        snapshot_id: QueryParam[str],
        request: Request,
    ) -> TableCoordinateManifest:
        return await self.coordinates.manifest(
            identity_from_request(request).subject, tenant_id, dataset_id, table_id, snapshot_id
        )

    @post_mapping("/cells")
    async def cells(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        body: Valid[Body[CoordinateCellRequest]],
        request: Request,
    ) -> TableCoordinateSelection:
        return await self.coordinates.cells(
            identity_from_request(request).subject, tenant_id, dataset_id, table_id, body
        )

    @get_mapping("/rows")
    async def rows(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        snapshot_id: QueryParam[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> TableRowRangePage:
        return await self.coordinates.rows(
            identity_from_request(request).subject,
            tenant_id,
            dataset_id,
            table_id,
            snapshot_id,
            page=page,
            page_size=page_size,
        )

    @get_mapping("/columns")
    async def columns(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        snapshot_id: QueryParam[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> TableColumnBindingPage:
        return await self.coordinates.columns(
            identity_from_request(request).subject,
            tenant_id,
            dataset_id,
            table_id,
            snapshot_id,
            page=page,
            page_size=page_size,
        )
