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

from koinon.catalog.errors import AccessDenied
from koinon.corporate_identity.challenges import CorporateLoginChallenges
from koinon.corporate_identity.dtos import (
    IdentityActivation,
    IdentityMappingInput,
    IdentityProviderInput,
    IdentityProviderPatch,
    IdentityRevision,
)
from koinon.corporate_identity.service import CorporateIdentityService
from koinon.security.identity import identity_from_request


def ordinary_identity(request):
    identity = identity_from_request(request)
    if (
        "koinon_token" in request.state.security_context.attributes
        or "koinon_token_id" in request.state.security_context.attributes
    ):
        raise AccessDenied(
            "Manage corporate access through your user identity.", code="INTERACTIVE_IDENTITY_REQUIRED"
        )
    return identity.subject


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/identity/providers")
class CorporateIdentityController:
    def __init__(self, identities: CorporateIdentityService, challenges: CorporateLoginChallenges):
        self.identities, self.challenges = identities, challenges

    @get_mapping("")
    async def list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        kind: QueryParam[str | None] = None,
        status: QueryParam[str | None] = None,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> dict:
        return await self.identities.page(
            ordinary_identity(request),
            tenant_id,
            q=q,
            kind=kind,
            status=status,
            page=page,
            page_size=page_size,
        )

    @post_mapping("", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[IdentityProviderInput]], request: Request
    ) -> dict:
        return (await self.identities.create(ordinary_identity(request), tenant_id, body)).model_dump(
            mode="json"
        )

    @get_mapping("/{provider_id}")
    async def get(self, tenant_id: PathVar[str], provider_id: PathVar[str], request: Request) -> dict:
        return (await self.identities.get(ordinary_identity(request), tenant_id, provider_id)).model_dump(
            mode="json"
        )

    @patch_mapping("/{provider_id}")
    async def update(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        body: Valid[Body[IdentityProviderPatch]],
        request: Request,
    ) -> dict:
        return (
            await self.identities.update(ordinary_identity(request), tenant_id, provider_id, body)
        ).model_dump(mode="json")

    @post_mapping("/{provider_id}/test", status_code=201)
    async def test(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        body: Valid[Body[IdentityRevision]],
        request: Request,
    ) -> dict:
        return (
            await self.challenges.create(
                ordinary_identity(request), tenant_id, provider_id, body.expected_revision
            )
        ).model_dump(mode="json")

    @get_mapping("/{provider_id}/tests/{validation_id}")
    async def test_status(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        validation_id: PathVar[str],
        request: Request,
    ) -> dict:
        return (
            await self.challenges.get(ordinary_identity(request), tenant_id, provider_id, validation_id)
        ).model_dump(mode="json")

    @get_mapping("/{provider_id}/groups")
    async def groups(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        limit: QueryParam[int] = 25,
        after: QueryParam[str] = "",
    ) -> dict:
        return await self.identities.groups(
            ordinary_identity(request), tenant_id, provider_id, q=q, limit=limit, after=after
        )

    @get_mapping("/{provider_id}/mappings")
    async def mappings(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        status: QueryParam[str] = "all",
        workspace_id: QueryParam[str | None] = None,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> dict:
        return await self.identities.list_mappings(
            ordinary_identity(request),
            tenant_id,
            provider_id,
            q=q,
            status=status,
            workspace_id=workspace_id,
            page=page,
            page_size=page_size,
        )

    @post_mapping("/{provider_id}/mappings", status_code=201)
    async def mapping_create(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        body: Valid[Body[IdentityMappingInput]],
        request: Request,
    ) -> dict:
        return await self.identities.save_mapping(ordinary_identity(request), tenant_id, provider_id, body)

    @patch_mapping("/{provider_id}/mappings/{mapping_id}")
    async def mapping_update(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        mapping_id: PathVar[str],
        body: Valid[Body[IdentityMappingInput]],
        request: Request,
    ) -> dict:
        return await self.identities.save_mapping(
            ordinary_identity(request), tenant_id, provider_id, body, mapping_id
        )

    @delete_mapping("/{provider_id}/mappings/{mapping_id}", status_code=204)
    async def mapping_remove(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        mapping_id: PathVar[str],
        expected_revision: QueryParam[int],
        request: Request,
    ) -> None:
        await self.identities.remove_mapping(
            ordinary_identity(request), tenant_id, provider_id, mapping_id, expected_revision
        )

    @post_mapping("/{provider_id}/activate")
    async def activate(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        body: Valid[Body[IdentityActivation]],
        request: Request,
    ) -> dict:
        return (
            await self.identities.activate(ordinary_identity(request), tenant_id, provider_id, body)
        ).model_dump(mode="json")

    @post_mapping("/{provider_id}/disable")
    async def disable(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        body: Valid[Body[IdentityRevision]],
        request: Request,
    ) -> dict:
        return (
            await self.identities.disable(
                ordinary_identity(request), tenant_id, provider_id, expected_revision=body.expected_revision
            )
        ).model_dump(mode="json")
