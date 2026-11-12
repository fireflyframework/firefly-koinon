# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-aware catalog detail without changing saved-default GET clients."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.catalog.mappers import entry_dto
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.read_dtos import ReaderReadInput
from koinon.integrations.content_sources.read_requests import reader_response
from koinon.integrations.content_sources.read_service import SourceReader


@rest_controller(name="catalog.read_controller")
@request_mapping("/api/v1/tenants/{tenant_id}/catalog")
class CatalogReadController:
    def __init__(self, catalog: CatalogService, reader: SourceReader):
        self.catalog, self.reader = catalog, reader

    @post_mapping("/{entry_id}/read")
    async def catalog_get_read(
        self,
        tenant_id: PathVar[str],
        entry_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            operation = await self.reader.entries(actor, tenant_id, (entry_id,))
            async with operation.read_fence():
                entry = await self.catalog.get(actor, tenant_id, entry_id)
            await operation.release()
            async with operation.read_fence():
                return entry_dto(entry)

        return await reader_response(self.reader, request, tenant_id, body, read)
