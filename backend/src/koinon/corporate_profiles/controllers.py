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

from koinon.corporate_identity.controllers import ordinary_identity
from koinon.corporate_profiles.dtos import (
    CorporateProfileRefresh,
    CorporateProfileRefreshInput,
    OrganizationPresentation,
    OrganizationPresentationInput,
)
from koinon.corporate_profiles.security import personal_identity
from koinon.corporate_profiles.service import CorporateProfileService
from koinon.profiles.controllers import browser_urls


def browser(value, request):
    return type(value).model_validate(browser_urls(value.model_dump(), request))


@rest_controller(name="corporate_profiles.controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class CorporateProfilesController:
    def __init__(self, profiles: CorporateProfileService):
        self.profiles = profiles

    @get_mapping("/organization/people/me/presentation")
    async def presentation(
        self, tenant_id: PathVar[str], request: Request, workspace_id: QueryParam[str | None] = None
    ) -> OrganizationPresentation:
        return browser(
            await self.profiles.presentation(
                personal_identity(request, tenant_id, workspace_id).subject,
                tenant_id,
                workspace_id=workspace_id,
            ),
            request,
        )

    @patch_mapping("/organization/people/me/presentation")
    async def update_presentation(
        self,
        tenant_id: PathVar[str],
        body: Valid[Body[OrganizationPresentationInput]],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
    ) -> OrganizationPresentation:
        return browser(
            await self.profiles.update_presentation(
                personal_identity(request, tenant_id, workspace_id, write=True).subject,
                tenant_id,
                body,
                workspace_id=workspace_id,
            ),
            request,
        )

    @post_mapping("/organization/people/me/profile-refresh", status_code=202)
    async def refresh_self(
        self,
        tenant_id: PathVar[str],
        body: Valid[Body[CorporateProfileRefreshInput]],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
    ) -> CorporateProfileRefresh:
        return await self.profiles.refresh_self(
            personal_identity(request, tenant_id, workspace_id, write=True).subject,
            tenant_id,
            workspace_id=workspace_id,
        )

    @post_mapping("/organization/people/{person_id}/profile-refresh", status_code=202)
    async def refresh_person(
        self,
        tenant_id: PathVar[str],
        person_id: PathVar[str],
        body: Valid[Body[CorporateProfileRefreshInput]],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
    ) -> CorporateProfileRefresh:
        if person_id == "me":
            return await self.refresh_self(tenant_id, body, request, workspace_id=workspace_id)
        return await self.profiles.refresh_person(
            ordinary_identity(request),
            tenant_id,
            person_id,
            workspace_id=workspace_id,
        )
