# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.kernel import GoneException
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    delete_mapping,
    get_mapping,
    post_mapping,
    request_mapping,
)
from pyfly.web.adapters.starlette.errors import global_exception_handler
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from koinon.evidence.http import private_json
from koinon.security.identity import identity_from_request
from koinon.sharing.dtos import ShareCreate, ShareReviewInput
from koinon.sharing.service import ConversationShares


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/shares")
class ShareController:
    def __init__(self, shares: ConversationShares):
        self.shares = shares

    @post_mapping("/reviews", status_code=201)
    async def review(
        self, tenant_id: PathVar[str], body: Valid[Body[ShareReviewInput]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.shares.preview(identity_from_request(request).subject, tenant_id, body), status=201
        )

    @post_mapping("", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[ShareCreate]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.shares.create(identity_from_request(request).subject, tenant_id, body), status=201
        )

    @get_mapping("")
    async def list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        status: QueryParam[str] = "all",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> JSONResponse:
        return private_json(
            await self.shares.page(
                identity_from_request(request).subject,
                tenant_id,
                q=q,
                status=status,
                page=page,
                page_size=page_size,
            )
        )

    @get_mapping("/{share_id}")
    async def get(self, tenant_id: PathVar[str], share_id: PathVar[str], request: Request) -> Response:
        try:
            return private_json(
                await self.shares.read(identity_from_request(request).subject, tenant_id, share_id)
            )
        except GoneException as error:
            response = await global_exception_handler(request, error)
            response.headers["Cache-Control"] = "private, no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

    @delete_mapping("/{share_id}", status_code=204)
    async def revoke(self, tenant_id: PathVar[str], share_id: PathVar[str], request: Request) -> None:
        await self.shares.revoke(identity_from_request(request).subject, tenant_id, share_id)
