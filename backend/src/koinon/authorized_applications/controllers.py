# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import PathVar, QueryParam, delete_mapping, get_mapping, request_mapping
from starlette.requests import Request

from koinon.authorized_applications.service import AuthorizedApplicationService
from koinon.tokens.controllers import interactive_identity


@rest_controller(name="authorized_applications.controller")
@request_mapping("/api/v1/authorized-applications")
class AuthorizedApplicationController:
    def __init__(self, applications: AuthorizedApplicationService):
        self.applications = applications

    @get_mapping("")
    async def list(
        self,
        request: Request,
        q: QueryParam[str] = "",
        status: QueryParam[str] = "all",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        sort: QueryParam[str] = "connected_at",
        order: QueryParam[str] = "desc",
    ) -> dict:
        return await self.applications.page(
            interactive_identity(request).subject,
            q=q,
            status=status,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
        )

    @get_mapping("/{application_id}")
    async def detail(self, application_id: PathVar[str], request: Request) -> dict:
        return await self.applications.detail(interactive_identity(request).subject, application_id)

    @delete_mapping("/{application_id}", status_code=204)
    async def revoke(self, application_id: PathVar[str], request: Request):
        await self.applications.revoke(interactive_identity(request).subject, application_id)
