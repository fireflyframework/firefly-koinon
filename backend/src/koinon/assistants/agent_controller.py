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

from koinon.assistants.configuration_service import AssistantConfigurationService
from koinon.assistants.dtos import AgentInput
from koinon.security.identity import identity_from_request


@rest_controller(name="assistants.agent-controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class AgentController:
    def __init__(self, assistants: AssistantConfigurationService):
        self.assistants = assistants

    @get_mapping("/agents")
    async def agents(
        self,
        tenant_id: PathVar[str],
        request: Request,
        q: QueryParam[str] = "",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
        status: QueryParam[str | None] = None,
        workspace_id: QueryParam[str | None] = None,
        project_id: QueryParam[str | None] = None,
        sort: QueryParam[str] = "name",
        order: QueryParam[str] = "asc",
    ) -> dict:
        return await self.assistants.agent_page(
            identity_from_request(request).subject,
            tenant_id,
            q=q,
            page=page,
            page_size=page_size,
            status=status.strip() or None if status is not None else None,
            sort=sort,
            order=order,
            workspace_id=workspace_id,
            project_id=project_id,
        )

    @post_mapping("/agents", status_code=201)
    async def agent_create(
        self, tenant_id: PathVar[str], body: Valid[Body[AgentInput]], request: Request
    ) -> dict:
        return await self.assistants.save_agent(
            identity_from_request(request).subject,
            tenant_id,
            body.model_dump(exclude_unset=True, exclude_none=True),
        )

    @patch_mapping("/agents/{agent_id}")
    async def agent_update(
        self, tenant_id: PathVar[str], agent_id: PathVar[str], body: Valid[Body[AgentInput]], request: Request
    ) -> dict:
        return await self.assistants.save_agent(
            identity_from_request(request).subject,
            tenant_id,
            body.model_dump(exclude_unset=True, exclude_none=True),
            agent_id,
        )

    @post_mapping("/agents/{agent_id}/validate")
    async def agent_validate(self, tenant_id: PathVar[str], agent_id: PathVar[str], request: Request) -> dict:
        return await self.assistants.validate_agent(
            identity_from_request(request).subject, tenant_id, agent_id
        )
