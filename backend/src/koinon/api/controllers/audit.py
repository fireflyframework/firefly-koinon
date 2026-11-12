# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.kernel import ServiceUnavailableException
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
        actor = identity_from_request(request).subject
        filters = dict(
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
        result = await self.catalog.audit_page(actor, tenant_id, **filters)
        actors = await self.profiles.author_summaries(
            {row.subject for row in result["items"]},
            actor=actor,
            tenant_id=tenant_id,
            permission="audit:read",
        )
        current = await self.catalog.audit_page(actor, tenant_id, **filters, _identities_only=True)
        if current["items"] != [row.id for row in result["items"]] or any(
            current[key] != result[key] for key in ("total", "page", "page_size", "pages")
        ):
            raise ServiceUnavailableException(
                "Audit history changed; refresh to continue", code="AUDIT_UNAVAILABLE"
            )
        return {**result, "items": [audit_dto(row) for row in result["items"]], "actors": actors}
