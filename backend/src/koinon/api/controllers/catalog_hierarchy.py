# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request

from koinon.catalog.hierarchy_dtos import CatalogMove
from koinon.catalog.hierarchy_service import CatalogHierarchyService
from koinon.catalog.mappers import entry_dto
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class CatalogHierarchyController:
    def __init__(self, hierarchy: CatalogHierarchyService):
        self.hierarchy = hierarchy

    @post_mapping("/tenants/{tenant_id}/catalog/{entry_id}/move")
    async def move(
        self,
        tenant_id: PathVar[str],
        entry_id: PathVar[str],
        body: Valid[Body[CatalogMove]],
        request: Request,
    ) -> dict:
        return entry_dto(
            await self.hierarchy.move(
                identity_from_request(request).subject, tenant_id, entry_id, **body.model_dump()
            )
        )
