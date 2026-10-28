# Copyright 2026 Firefly Software Foundation & Firefly Software Solutions Inc.
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import PathVar, QueryParam, get_mapping, request_mapping
from starlette.requests import Request

from koinon.knowledge.provenance.dtos import TableProvenance, TableSnapshotPage
from koinon.knowledge.provenance.service import TableProvenanceService
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.table_provenance")
@request_mapping("/api/v1/tenants/{tenant_id}/datasets/{dataset_id}/tables/{table_id}")
class TableProvenanceController:
    def __init__(self, provenance: TableProvenanceService):
        self.provenance = provenance

    @get_mapping("/provenance")
    async def snapshot(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        snapshot_id: QueryParam[str],
        request: Request,
    ) -> TableProvenance:
        return await self.provenance.snapshot(
            identity_from_request(request).subject, tenant_id, dataset_id, table_id, snapshot_id
        )

    @get_mapping("/snapshots")
    async def history(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        table_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> TableSnapshotPage:
        return await self.provenance.history(
            identity_from_request(request).subject,
            tenant_id,
            dataset_id,
            table_id,
            page=page,
            page_size=page_size,
        )
