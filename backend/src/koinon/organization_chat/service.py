# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.assistants.configuration_service import AssistantConfigurationService
from koinon.assistants.repositories import AgentRepository
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.organization_chat.dtos import OrganizationChatSettings
from koinon.organization_chat.repositories import OrganizationChatRepository


@service(name="organization_chat.service")
class OrganizationChatService:
    def __init__(
        self,
        catalog: CatalogService,
        settings: OrganizationChatRepository,
        agents: AgentRepository,
        configuration: AssistantConfigurationService,
        scopes: KnowledgeScopePolicy,
    ):
        self.catalog, self.settings, self.agents = catalog, settings, agents
        self.configuration, self.scopes = configuration, scopes

    async def _read_scope(self, subject, tenant_id, workspace_id, project_id):
        requested = {
            key: value
            for key, value in dict(workspace_id=workspace_id, project_id=project_id).items()
            if value is not None
        }
        try:
            await self.scopes.validate_scope(subject, tenant_id, requested)
            return True
        except AccessDenied:
            if requested:
                raise
            await self.catalog.authorize(subject, tenant_id, "agents:write")
            return False

    async def _view(self, tenant_id, row, can_use=True):
        agent_id = row.default_agent_id if row else None
        result = dict(
            tenant_id=tenant_id,
            default_agent_id=agent_id,
            revision=row.revision if row else 0,
            configured=False,
            can_run=False,
            status="unconfigured",
        )
        if agent_id:
            agent = await self.agents.find_by_id(agent_id)
            result["status"] = "unavailable"
            if agent is not None and agent.tenant_id == tenant_id and not agent.scope:
                try:
                    metadata = await self.configuration.agent_dto(agent)
                except AccessDenied:
                    return OrganizationChatSettings.model_validate(result).model_dump()
                result.update({key: metadata[key] for key in ("configured", "can_run", "status")})
                result["can_run"] = bool(result["can_run"] and can_use)
        return OrganizationChatSettings.model_validate(result).model_dump()

    @transactional(read_only=True)
    async def get(self, subject, tenant_id, *, workspace_id=None, project_id=None):
        can_use = await self._read_scope(subject, tenant_id, workspace_id, project_id)
        return await self._view(tenant_id, await self.settings.current(tenant_id), can_use)

    @transactional
    async def update(self, subject, tenant_id, default_agent_id, expected_revision):
        await self.catalog.authorize(subject, tenant_id, "agents:write")
        if type(expected_revision) is not int or not 0 <= expected_revision <= 2147483646:
            raise InvalidRequestException("Supply the current settings revision", code="INVALID_REVISION")
        if default_agent_id is not None:
            agent = await self.agents.find_by_id(default_agent_id)
            if agent is None or agent.tenant_id != tenant_id:
                raise AccessDenied("Agent is unavailable in this organization", code="ACCESS_DENIED")
            if agent.scope:
                raise InvalidRequestException(
                    "Choose an organization-wide agent", code="INVALID_DEFAULT_AGENT"
                )
        changed = await self.settings.compare_and_swap(
            tenant_id, default_agent_id, expected_revision, subject, datetime.now(UTC)
        )
        if not changed:
            raise ConflictException(
                "Organization chat settings changed. Reload and try again.", code="ORGANIZATION_CHAT_CHANGED"
            )
        await self.catalog._audit(
            subject,
            tenant_id,
            "organization_chat.updated",
            tenant_id,
            dict(default_agent_id=default_agent_id, revision=expected_revision + 1),
        )
        can_use = "chat:use" in await self.catalog.permissions(subject, tenant_id)
        return await self._view(tenant_id, await self.settings.current(tenant_id), can_use)
