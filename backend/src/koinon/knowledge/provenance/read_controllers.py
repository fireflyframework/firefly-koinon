# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed reader-aware reads preserve existing domain services and release fences."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.integrations.content_sources.read_requests import reader_response
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.knowledge.provenance.coordinate_service import TableCoordinateService
from koinon.knowledge.provenance.read_dtos import (
    SnapshotHistoryReadInput,
    SnapshotPageReadInput,
    SnapshotReadInput,
)
from koinon.knowledge.provenance.service import TableProvenanceService


@rest_controller(name="knowledge.table_provenance_read")
@request_mapping("/api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}")
class TableProvenanceReadController:
    def __init__(
        self, provenance: TableProvenanceService, coordinates: TableCoordinateService, reader: SourceReader
    ):
        self.provenance, self.coordinates = provenance, coordinates
        self.reader = reader

    @post_mapping("/provenance/read")
    async def snapshot_read(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        body: Valid[Body[SnapshotReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.provenance.snapshot(actor, tenant_id, dataset_id, table_id, body.snapshot_id)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/snapshots/read")
    async def history_read(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        body: Valid[Body[SnapshotHistoryReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.provenance.read_history(actor, tenant_id, dataset_id, table_id, body)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/coordinates/read")
    async def manifest_read(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        body: Valid[Body[SnapshotReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.coordinates.manifest(actor, tenant_id, dataset_id, table_id, body.snapshot_id)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/coordinates/rows/read")
    async def rows_read(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        body: Valid[Body[SnapshotPageReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.coordinates.rows(
                actor,
                tenant_id,
                dataset_id,
                table_id,
                body.snapshot_id,
                page=body.page,
                page_size=body.page_size,
            )

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/coordinates/columns/read")
    async def columns_read(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        body: Valid[Body[SnapshotPageReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.coordinates.columns(
                actor,
                tenant_id,
                dataset_id,
                table_id,
                body.snapshot_id,
                page=body.page,
                page_size=body.page_size,
            )

        return await reader_response(self.reader, request, tenant_id, body, read)
