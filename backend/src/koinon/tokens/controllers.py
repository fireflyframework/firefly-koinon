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
    post_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.catalog.errors import AccessDenied
from koinon.security.identity import identity_from_request
from koinon.tokens.dtos import TokenInput
from koinon.tokens.service import PersonalTokenService


def interactive_identity(request):
    identity = identity_from_request(request)
    if request.state.security_context.attributes.get("koinon_token_id"):
        raise AccessDenied(
            "Manage API tokens through your user session", code="INTERACTIVE_IDENTITY_REQUIRED"
        )
    return identity


@rest_controller(name="tokens.controller")
@request_mapping("/api/v1/tokens")
class PersonalTokenController:
    def __init__(self, tokens: PersonalTokenService):
        self.tokens = tokens

    @get_mapping("")
    async def list(
        self,
        request: Request,
        q: QueryParam[str] = "",
        status: QueryParam[str] = "all",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        sort: QueryParam[str] = "created_at",
        order: QueryParam[str] = "desc",
    ) -> dict:
        return await self.tokens.page(
            interactive_identity(request).subject,
            q=q,
            status=status,
            page=page,
            page_size=page_size,
            sort=sort,
            order=order,
        )

    @get_mapping("/scopes")
    async def scopes(
        self, tenant_id: QueryParam[str], request: Request, workspace_id: QueryParam[str | None] = None
    ) -> dict:
        return await self.tokens.scope_options(interactive_identity(request).subject, tenant_id, workspace_id)

    @post_mapping("", status_code=201)
    async def create(self, body: Valid[Body[TokenInput]], request: Request) -> dict:
        return await self.tokens.create(interactive_identity(request).subject, body.model_dump())

    @delete_mapping("/{token_id}", status_code=204)
    async def revoke(self, token_id: PathVar[str], request: Request):
        await self.tokens.revoke(interactive_identity(request).subject, token_id)
