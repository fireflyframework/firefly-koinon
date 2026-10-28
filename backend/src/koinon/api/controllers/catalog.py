# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    delete_mapping,
    get_mapping,
    patch_mapping,
    post_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.catalog.dtos import CatalogCreate, CatalogPatch
from koinon.catalog.mappers import entry_dto
from koinon.catalog.service import CatalogService
from koinon.profiles.service import ProfileService
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class CatalogController:
    def __init__(self, catalog: CatalogService, profiles: ProfileService):
        self.catalog, self.profiles = catalog, profiles

    @get_mapping("/tenants/{tenant_id}/catalog")
    async def catalog_list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        kind: QueryParam[str | None] = None,
        parent_id: QueryParam[str | None] = None,
        workspace_id: QueryParam[str | None] = None,
        project_id: QueryParam[str | None] = None,
        include_archived: QueryParam[bool] = False,
        view: QueryParam[str] = "raw",
        q: QueryParam[str] = "",
        status: QueryParam[str | None] = None,
        format: QueryParam[str | None] = None,
        tag: QueryParam[str | None] = None,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 100,
        sort: QueryParam[str] = "name",
        order: QueryParam[str] = "asc",
    ) -> dict:
        result = await self.catalog.page(
            identity_from_request(request).subject,
            tenant_id,
            kind=kind,
            parent_id=parent_id,
            workspace_id=workspace_id,
            project_id=project_id,
            include_archived=include_archived,
            view=view,
            q=q,
            status=status,
            format=format,
            tag=tag,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
        )
        subjects = {
            actor for entry in result["items"] for actor in (entry.created_by, entry.updated_by) if actor
        }
        actors = await self.profiles.author_summaries(subjects)
        return {**result, "items": [entry_dto(entry) for entry in result["items"]], "actors": actors}

    @post_mapping("/tenants/{tenant_id}/catalog", status_code=201)
    async def catalog_create(
        self, tenant_id: PathVar[str], body: Valid[Body[CatalogCreate]], request: Request
    ) -> dict:
        entry = await self.catalog.create(
            identity_from_request(request).subject, tenant_id, **body.model_dump()
        )
        return entry_dto(entry)

    @get_mapping("/tenants/{tenant_id}/catalog/{entry_id}")
    async def catalog_get(self, tenant_id: PathVar[str], entry_id: PathVar[str], request: Request) -> dict:
        return entry_dto(await self.catalog.get(identity_from_request(request).subject, tenant_id, entry_id))

    @patch_mapping("/tenants/{tenant_id}/catalog/{entry_id}")
    async def catalog_patch(
        self,
        tenant_id: PathVar[str],
        entry_id: PathVar[str],
        body: Valid[Body[CatalogPatch]],
        request: Request,
    ) -> dict:
        entry = await self.catalog.update(
            identity_from_request(request).subject,
            tenant_id,
            entry_id,
            body.model_dump(exclude_unset=True, exclude_none=True),
        )
        return entry_dto(entry)

    @post_mapping("/tenants/{tenant_id}/catalog/{entry_id}/archive")
    async def catalog_archive(
        self, tenant_id: PathVar[str], entry_id: PathVar[str], request: Request
    ) -> dict:
        return entry_dto(
            await self.catalog.archive(identity_from_request(request).subject, tenant_id, entry_id)
        )

    @post_mapping("/tenants/{tenant_id}/catalog/{entry_id}/restore")
    async def catalog_restore(
        self, tenant_id: PathVar[str], entry_id: PathVar[str], request: Request
    ) -> dict:
        return entry_dto(
            await self.catalog.restore(identity_from_request(request).subject, tenant_id, entry_id)
        )

    @delete_mapping("/tenants/{tenant_id}/catalog/{entry_id}", status_code=204)
    async def catalog_delete(self, tenant_id: PathVar[str], entry_id: PathVar[str], request: Request) -> None:
        await self.catalog.delete(identity_from_request(request).subject, tenant_id, entry_id)
