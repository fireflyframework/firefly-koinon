# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, get_mapping, post_mapping, put_mapping, request_mapping
from starlette.requests import Request

from koinon.organization_branding.dtos import (
    BrandingResetInput,
    BrandingValues,
    OrganizationBranding,
    OrganizationBrandingInput,
)
from koinon.organization_branding.service import OrganizationBrandingService
from koinon.security.identity import identity_from_request


@rest_controller(name="organization_branding.defaults_controller")
@request_mapping("/api/v1/branding")
class BrandingDefaultsController:
    def __init__(self, settings: OrganizationBrandingService):
        self.settings = settings

    @get_mapping("/defaults")
    async def defaults(self) -> BrandingValues:
        return self.settings.defaults


@rest_controller(name="organization_branding.controller")
@request_mapping("/api/v1/tenants/{tenant_id}/branding")
class OrganizationBrandingController:
    def __init__(self, settings: OrganizationBrandingService):
        self.settings = settings

    @get_mapping("")
    async def get(self, tenant_id: PathVar[str], request: Request) -> OrganizationBranding:
        return await self.settings.get(identity_from_request(request).subject, tenant_id)

    @put_mapping("")
    async def update(
        self, tenant_id: PathVar[str], body: Valid[Body[OrganizationBrandingInput]], request: Request
    ) -> OrganizationBranding:
        return await self.settings.update(identity_from_request(request).subject, tenant_id, body)

    @post_mapping("/reset")
    async def reset(
        self, tenant_id: PathVar[str], body: Valid[Body[BrandingResetInput]], request: Request
    ) -> OrganizationBranding:
        return await self.settings.reset(
            identity_from_request(request).subject, tenant_id, body.expected_revision
        )
