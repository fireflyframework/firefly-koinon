# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, get_mapping, put_mapping, request_mapping
from starlette.requests import Request

from koinon.organization_knowledge.dtos import (
    OrganizationKnowledgeSettings,
    OrganizationKnowledgeSettingsInput,
)
from koinon.organization_knowledge.service import OrganizationKnowledgeService
from koinon.security.identity import identity_from_request


@rest_controller(name="organization_knowledge.controller")
@request_mapping("/api/v1/tenants/{tenant_id}/knowledge/settings")
class OrganizationKnowledgeController:
    def __init__(self, settings: OrganizationKnowledgeService):
        self.settings = settings

    @get_mapping("")
    async def get(self, tenant_id: PathVar[str], request: Request) -> OrganizationKnowledgeSettings:
        return await self.settings.get(identity_from_request(request).subject, tenant_id)

    @put_mapping("")
    async def update(
        self, tenant_id: PathVar[str], body: Valid[Body[OrganizationKnowledgeSettingsInput]], request: Request
    ) -> OrganizationKnowledgeSettings:
        return await self.settings.update(identity_from_request(request).subject, tenant_id, body)
