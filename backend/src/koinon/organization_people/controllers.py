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
    put_mapping,
    request_mapping,
)
from starlette.requests import Request
from starlette.responses import Response

from koinon.corporate_identity.controllers import ordinary_identity
from koinon.organization_people.dtos import (
    OrganizationDirectorySettings,
    OrganizationDirectorySettingsInput,
    OrganizationPerson,
    OrganizationPersonCreate,
    OrganizationPersonPage,
    OrganizationPersonPatch,
    OrganizationProfileMapping,
    OrganizationProfileMappingInput,
    OrganizationUnit,
    OrganizationUnitInput,
    OrganizationUnitPage,
    OrganizationUnitPatch,
)
from koinon.organization_people.security import organization_identity, own_identity
from koinon.organization_people.service import OrganizationPeopleService
from koinon.profiles.controllers import browser_urls, image_response


def browser(value, request):
    return type(value).model_validate(browser_urls(value.model_dump(), request))


@rest_controller(name="organization_people.controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class OrganizationPeopleController:
    def __init__(self, people: OrganizationPeopleService):
        self.people = people

    @get_mapping("/organization/people/me")
    async def self(
        self, tenant_id: PathVar[str], request: Request, workspace_id: QueryParam[str | None] = None
    ) -> OrganizationPerson:
        return browser(
            await self.people.self(own_identity(request).subject, tenant_id, workspace_id=workspace_id),
            request,
        )

    @get_mapping("/organization/people")
    async def page(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        q: QueryParam[str] = "",
        job_title: QueryParam[str] = "",
        unit_id: QueryParam[str | None] = None,
        department_id: QueryParam[str | None] = None,
        manager_id: QueryParam[str | None] = None,
        unassigned: QueryParam[bool] = False,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> OrganizationPersonPage:
        actor = organization_identity(request, tenant_id, workspace_id)
        return browser(
            await self.people.page(
                actor.subject,
                tenant_id,
                workspace_id=workspace_id,
                q=q,
                job_title=job_title,
                unit_id=unit_id,
                department_id=department_id,
                manager_id=manager_id,
                unassigned=unassigned,
                page=page,
                page_size=page_size,
            ),
            request,
        )

    @post_mapping("/organization/people", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[OrganizationPersonCreate]], request: Request
    ) -> OrganizationPerson:
        return browser(
            await self.people.create(
                organization_identity(request, tenant_id, write=True).subject, tenant_id, body
            ),
            request,
        )

    @get_mapping("/organization/people/{person_id}")
    async def get(
        self,
        tenant_id: PathVar[str],
        person_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
    ) -> OrganizationPerson:
        if person_id == "me":
            return await self.self(tenant_id, request, workspace_id=workspace_id)
        return browser(
            await self.people.get(
                organization_identity(request, tenant_id, workspace_id).subject,
                tenant_id,
                person_id,
                workspace_id=workspace_id,
            ),
            request,
        )

    @patch_mapping("/organization/people/{person_id}")
    async def update(
        self,
        tenant_id: PathVar[str],
        person_id: PathVar[str],
        body: Valid[Body[OrganizationPersonPatch]],
        request: Request,
    ) -> OrganizationPerson:
        return browser(
            await self.people.update(
                organization_identity(request, tenant_id, write=True).subject, tenant_id, person_id, body
            ),
            request,
        )

    @get_mapping("/organization/people/{person_id}/avatar")
    async def avatar(
        self,
        tenant_id: PathVar[str],
        person_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
    ) -> Response:
        content = await self.people.avatar(
            organization_identity(request, tenant_id, workspace_id).subject,
            tenant_id,
            person_id,
            workspace_id=workspace_id,
        )
        return image_response(content, request)

    @get_mapping("/organization/people/{person_id}/reports")
    async def reports(
        self,
        tenant_id: PathVar[str],
        person_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> OrganizationPersonPage:
        return browser(
            await self.people.reports(
                organization_identity(request, tenant_id, workspace_id).subject,
                tenant_id,
                person_id,
                workspace_id=workspace_id,
                page=page,
                page_size=page_size,
            ),
            request,
        )

    @get_mapping("/organization/units")
    async def units(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        parent_id: QueryParam[str | None] = None,
        q: QueryParam[str] = "",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> OrganizationUnitPage:
        return await self.people.units(
            organization_identity(request, tenant_id, workspace_id).subject,
            tenant_id,
            workspace_id=workspace_id,
            parent_id=parent_id,
            q=q,
            page=page,
            page_size=page_size,
        )

    @post_mapping("/organization/units", status_code=201)
    async def create_unit(
        self, tenant_id: PathVar[str], body: Valid[Body[OrganizationUnitInput]], request: Request
    ) -> OrganizationUnit:
        return await self.people.create_unit(
            organization_identity(request, tenant_id, write=True).subject, tenant_id, body
        )

    @patch_mapping("/organization/units/{unit_id}")
    async def update_unit(
        self,
        tenant_id: PathVar[str],
        unit_id: PathVar[str],
        body: Valid[Body[OrganizationUnitPatch]],
        request: Request,
    ) -> OrganizationUnit:
        return await self.people.update_unit(
            organization_identity(request, tenant_id, write=True).subject, tenant_id, unit_id, body
        )

    @delete_mapping("/organization/units/{unit_id}", status_code=204)
    async def delete_unit(
        self,
        tenant_id: PathVar[str],
        unit_id: PathVar[str],
        request: Request,
        expected_revision: QueryParam[int],
    ) -> None:
        await self.people.delete_unit(
            organization_identity(request, tenant_id, write=True).subject,
            tenant_id,
            unit_id,
            expected_revision,
        )

    @get_mapping("/organization/directory-settings")
    async def settings(self, tenant_id: PathVar[str], request: Request) -> OrganizationDirectorySettings:
        return await self.people.settings(own_identity(request).subject, tenant_id)

    @patch_mapping("/organization/directory-settings")
    async def update_settings(
        self, tenant_id: PathVar[str], body: Valid[Body[OrganizationDirectorySettingsInput]], request: Request
    ) -> OrganizationDirectorySettings:
        return await self.people.update_settings(
            organization_identity(request, tenant_id, write=True).subject, tenant_id, body
        )

    @get_mapping("/organization/profile-mappings/{provider_id}")
    async def mapping(
        self, tenant_id: PathVar[str], provider_id: PathVar[str], request: Request
    ) -> OrganizationProfileMapping:
        return await self.people.mapping(ordinary_identity(request), tenant_id, provider_id)

    @put_mapping("/organization/profile-mappings/{provider_id}")
    async def update_mapping(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        body: Valid[Body[OrganizationProfileMappingInput]],
        request: Request,
    ) -> OrganizationProfileMapping:
        return await self.people.update_mapping(ordinary_identity(request), tenant_id, provider_id, body)
