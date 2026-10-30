# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    get_mapping,
    patch_mapping,
    post_mapping,
    request_mapping,
)
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.corporate_identity.controllers import ordinary_identity
from koinon.evidence.http import private_json
from koinon.mcp.connection import McpConnectionService
from koinon.mcp_applications.dtos import (
    McpOAuthClientInput,
    McpOAuthClientPage,
    McpOAuthClientPatch,
    McpOAuthClientRevision,
)
from koinon.mcp_applications.service import McpOAuthClientRegistry
from koinon.security.identity import identity_from_request


@rest_controller(name="mcp.applications.connection")
@request_mapping("/api/v1/tenants/{tenant_id}/mcp")
class McpOrganizationConnectionController:
    def __init__(self, connection: McpConnectionService):
        self.connection = connection

    @get_mapping("/connection")
    async def get(self, tenant_id: PathVar[str], request: Request) -> JSONResponse:
        return private_json(
            await self.connection.organization_descriptor(identity_from_request(request).subject, tenant_id)
        )


@rest_controller(name="mcp.applications.controller")
@request_mapping("/api/v1/tenants/{tenant_id}/mcp/oauth-clients")
class McpOAuthClientController:
    def __init__(self, applications: McpOAuthClientRegistry):
        self.applications = applications

    @get_mapping("/readiness")
    async def readiness(self, tenant_id: PathVar[str], request: Request) -> JSONResponse:
        return private_json(await self.applications.readiness(ordinary_identity(request), tenant_id))

    @get_mapping("")
    async def page(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        status: QueryParam[str] = "all",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        sort: QueryParam[str] = "name",
        order: QueryParam[str] = "asc",
    ) -> JSONResponse:
        return private_json(
            McpOAuthClientPage.model_validate(
                await self.applications.page(
                    ordinary_identity(request),
                    tenant_id,
                    q=q,
                    status=status,
                    page=page,
                    page_size=page_size,
                    sort=sort,
                    order=order,
                )
            )
        )

    @post_mapping("", status_code=201)
    async def create(
        self,
        tenant_id: PathVar[str],
        body: Valid[Body[McpOAuthClientInput]],
        request: Request,
    ) -> JSONResponse:
        return private_json(
            await self.applications.create(ordinary_identity(request), tenant_id, body),
            status=201,
        )

    @get_mapping("/{client_id}")
    async def retrieve(
        self,
        tenant_id: PathVar[str],
        client_id: PathVar[str],
        request: Request,
    ) -> JSONResponse:
        return private_json(await self.applications.get(ordinary_identity(request), tenant_id, client_id))

    @patch_mapping("/{client_id}")
    async def update(
        self,
        tenant_id: PathVar[str],
        client_id: PathVar[str],
        body: Valid[Body[McpOAuthClientPatch]],
        request: Request,
    ) -> JSONResponse:
        return private_json(
            await self.applications.update(
                ordinary_identity(request),
                tenant_id,
                client_id,
                body,
            )
        )

    @post_mapping("/{client_id}/rotate-secret")
    async def rotate_secret(
        self,
        tenant_id: PathVar[str],
        client_id: PathVar[str],
        body: Valid[Body[McpOAuthClientRevision]],
        request: Request,
    ) -> JSONResponse:
        return private_json(
            await self.applications.rotate_secret(
                ordinary_identity(request),
                tenant_id,
                client_id,
                body.expected_revision,
            )
        )
