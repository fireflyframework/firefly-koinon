# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.assistants.configuration_service import AssistantConfigurationService
from koinon.assistants.repositories import AgentRepository
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.assistants.settings import AssistantSettings
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.organization_chat.dtos import (
    OrganizationChatSettings,
    OrganizationMemoryPolicy,
    OrganizationMemoryPolicyInput,
)
from koinon.organization_chat.memory_policy import effective_memory_policy
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
        assistant_settings: AssistantSettings | None = None,
    ):
        self.catalog, self.settings, self.agents = catalog, settings, agents
        self.configuration, self.scopes = configuration, scopes
        self.assistant_settings = assistant_settings or AssistantSettings()

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
            memory=effective_memory_policy(row.memory_policy_json if row else None, self.assistant_settings),
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
    async def update(
        self,
        subject,
        tenant_id,
        default_agent_id,
        expected_revision,
        *,
        memory: OrganizationMemoryPolicyInput | None = None,
    ):
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
        if memory is not None:
            requested = memory.model_dump(exclude_unset=True)
            hard = {
                "max_history_messages": min(40, max(0, self.assistant_settings.max_history_messages)),
                "max_history_tokens": min(65536, max(0, self.assistant_settings.max_history_tokens)),
                "max_project_memory_messages": min(40, max(0, self.assistant_settings.max_history_messages)),
            }
            if any(key in requested and requested[key] > limit for key, limit in hard.items()):
                raise InvalidRequestException(
                    "Memory limits cannot exceed deployment bounds", code="MEMORY_LIMIT_EXCEEDED"
                )
            current = await self.settings.current(tenant_id)
            previous = (
                OrganizationMemoryPolicy.model_validate(current.memory_policy_json)
                if current and current.memory_policy_json is not None
                else OrganizationMemoryPolicy()
            )
            try:
                memory = OrganizationMemoryPolicy.model_validate({**previous.model_dump(), **requested})
            except ValidationError as exc:
                raise InvalidRequestException(
                    "Project memory cannot exceed the total conversation history limit",
                    code="MEMORY_LIMIT_EXCEEDED",
                ) from exc
        changed = await self.settings.compare_and_swap(
            tenant_id,
            default_agent_id,
            expected_revision,
            subject,
            datetime.now(UTC),
            memory=memory.model_dump() if memory is not None else None,
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
            dict(
                default_agent_id=default_agent_id,
                revision=expected_revision + 1,
                **({"memory": memory.model_dump()} if memory is not None else {}),
            ),
        )
        can_use = "chat:use" in await self.catalog.permissions(subject, tenant_id)
        return await self._view(tenant_id, await self.settings.current(tenant_id), can_use)
