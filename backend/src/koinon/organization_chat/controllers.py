# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, put_mapping, request_mapping
from starlette.requests import Request

from koinon.organization_chat.dtos import OrganizationChatSettingsInput
from koinon.organization_chat.service import OrganizationChatService
from koinon.security.identity import identity_from_request


@rest_controller(name="organization_chat.controller")
@request_mapping("/api/v1/tenants/{tenant_id}/chat/settings")
class OrganizationChatController:
    def __init__(self, settings: OrganizationChatService):
        self.settings = settings

    @get_mapping("")
    async def get(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        project_id: QueryParam[str | None] = None,
    ) -> dict:
        return await self.settings.get(
            identity_from_request(request).subject,
            tenant_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    @put_mapping("")
    async def update(
        self, tenant_id: PathVar[str], body: Valid[Body[OrganizationChatSettingsInput]], request: Request
    ) -> dict:
        return await self.settings.update(
            identity_from_request(request).subject, tenant_id, body.default_agent_id, body.expected_revision
        )
