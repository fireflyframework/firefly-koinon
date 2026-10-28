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
from starlette.responses import JSONResponse

from koinon.catalog.dtos import MemberCreate, MemberPatch
from koinon.catalog.errors import AccessDenied
from koinon.catalog.invitation_dtos import InvitationInput, InvitationToken
from koinon.catalog.invitation_service import InvitationService
from koinon.catalog.mappers import member_dto
from koinon.catalog.service import CatalogService
from koinon.profiles.service import ProfileService
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class MembershipController:
    def __init__(self, catalog: CatalogService, profiles: ProfileService, invitations: InvitationService):
        self.catalog, self.profiles, self.invitations = catalog, profiles, invitations

    @get_mapping("/tenants/{tenant_id}/members")
    async def members(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        q: QueryParam[str] = "",
        role: QueryParam[str | None] = None,
        scope: QueryParam[str] = "all",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> dict:
        result = await self.catalog.member_page(
            identity_from_request(request).subject,
            tenant_id,
            workspace_id=workspace_id,
            q=q,
            role=role,
            scope=scope,
            page=page,
            page_size=page_size,
        )
        actors = {
            subject: await self.profiles.author_summary(subject)
            for subject in dict.fromkeys(row.subject for row in result["items"])
        }
        return {**result, "items": [member_dto(member) for member in result["items"]], "actors": actors}

    @post_mapping("/tenants/{tenant_id}/members", status_code=201)
    async def member_create(
        self, tenant_id: PathVar[str], body: Valid[Body[MemberCreate]], request: Request
    ) -> dict:
        return member_dto(
            await self.catalog.create_member(
                identity_from_request(request).subject, tenant_id, **body.model_dump()
            )
        )

    @patch_mapping("/tenants/{tenant_id}/members/{member_id}")
    async def member_patch(
        self,
        tenant_id: PathVar[str],
        member_id: PathVar[str],
        body: Valid[Body[MemberPatch]],
        request: Request,
    ) -> dict:
        return member_dto(
            await self.catalog.update_member(
                identity_from_request(request).subject,
                tenant_id,
                member_id,
                **body.model_dump(exclude_unset=True, exclude_none=True),
            )
        )

    @delete_mapping("/tenants/{tenant_id}/members/{member_id}", status_code=204)
    async def member_delete(self, tenant_id: PathVar[str], member_id: PathVar[str], request: Request) -> None:
        await self.catalog.update_member(
            identity_from_request(request).subject, tenant_id, member_id, active=False
        )

    @get_mapping("/tenants/{tenant_id}/invitations")
    async def invitations_list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        status: QueryParam[str] = "pending",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> dict:
        return await self.invitations.page(
            invitation_identity(request),
            tenant_id,
            workspace_id=workspace_id,
            status=status,
            page=page,
            page_size=page_size,
        )

    @post_mapping("/tenants/{tenant_id}/invitations", status_code=201)
    async def invitation_create(
        self, tenant_id: PathVar[str], body: Valid[Body[InvitationInput]], request: Request
    ) -> JSONResponse:
        created = await self.invitations.create(invitation_identity(request), tenant_id, **body.model_dump())
        return JSONResponse(
            {
                "invitation": created.invitation.model_dump(mode="json"),
                "token": created.token.get_secret_value(),
            },
            status_code=201,
            headers={"Cache-Control": "no-store"},
        )

    @delete_mapping("/tenants/{tenant_id}/invitations/{invitation_id}", status_code=204)
    async def invitation_revoke(
        self, tenant_id: PathVar[str], invitation_id: PathVar[str], request: Request
    ) -> None:
        await self.invitations.revoke(invitation_identity(request), tenant_id, invitation_id)

    @post_mapping("/invitations/inspect")
    async def invitation_inspect(self, body: Valid[Body[InvitationToken]], request: Request) -> JSONResponse:
        return JSONResponse(
            await self.invitations.inspect(invitation_identity(request), body.token.get_secret_value()),
            headers={"Cache-Control": "no-store"},
        )

    @post_mapping("/invitations/redeem", status_code=201)
    async def invitation_redeem(self, body: Valid[Body[InvitationToken]], request: Request) -> JSONResponse:
        member = await self.invitations.redeem(invitation_identity(request), body.token.get_secret_value())
        return JSONResponse(member_dto(member), status_code=201, headers={"Cache-Control": "no-store"})


def invitation_identity(request: Request) -> str:
    identity = identity_from_request(request)
    attributes = request.state.security_context.attributes
    if "koinon_token_id" in attributes or "koinon_token" in attributes:
        raise AccessDenied(
            "Manage invitations through your user session", code="INTERACTIVE_IDENTITY_REQUIRED"
        )
    return identity.subject
