# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import PathVar, QueryParam, get_mapping, request_mapping
from starlette.requests import Request

from koinon.catalog.mappers import audit_dto
from koinon.catalog.service import CatalogService
from koinon.profiles.service import ProfileService
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class AuditController:
    def __init__(self, catalog: CatalogService, profiles: ProfileService):
        self.catalog, self.profiles = catalog, profiles

    @get_mapping("/tenants/{tenant_id}/audit")
    async def audit(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        action: QueryParam[str | None] = None,
        subject: QueryParam[str | None] = None,
        from_date: QueryParam[str | None] = None,
        through_date: QueryParam[str | None] = None,
        time_zone: QueryParam[str] = "UTC",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        sort: QueryParam[str] = "created_at",
        order: QueryParam[str] = "desc",
    ) -> dict:
        result = await self.catalog.audit_page(
            identity_from_request(request).subject,
            tenant_id,
            q=q,
            action=action,
            subject=subject,
            from_date=from_date,
            through_date=through_date,
            time_zone=time_zone,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
        )
        actors = {
            subject: await self.profiles.author_summary(subject)
            for subject in dict.fromkeys(row.subject for row in result["items"])
        }
        return {**result, "items": [audit_dto(row) for row in result["items"]], "actors": actors}
