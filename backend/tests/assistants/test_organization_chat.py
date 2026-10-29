# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest
from pyfly.kernel import ConflictException, InvalidRequestException
from test_service import assistants as assistants
from test_service import configured

from koinon.organization_chat.entities import OrganizationChatSetting  # noqa: F401


async def settings_service(context):
    from koinon.assistants.configuration_service import AssistantConfigurationService
    from koinon.assistants.repositories import AgentRepository
    from koinon.assistants.scope import KnowledgeScopePolicy
    from koinon.catalog.service import CatalogService
    from koinon.organization_chat.repositories import OrganizationChatRepository
    from koinon.organization_chat.service import OrganizationChatService

    return OrganizationChatService(
        context.get_bean(CatalogService),
        OrganizationChatRepository(),
        context.get_bean(AgentRepository),
        context.get_bean(AssistantConfigurationService),
        context.get_bean(KnowledgeScopePolicy),
    )


async def test_default_is_persisted_per_organization_and_clear_never_falls_back(assistants):
    service, context = assistants
    settings = await settings_service(context)
    assert await settings.get("issuer|viewer", "north") == dict(
        tenant_id="north",
        default_agent_id=None,
        revision=0,
        configured=False,
        can_run=False,
        status="unconfigured",
    )
    _, agent = await configured(service)
    selected = await settings.update("issuer|admin", "north", agent["id"], 0)
    assert selected["default_agent_id"] == agent["id"] and selected["revision"] == 1
    assert (await settings.get("issuer|viewer", "north")) == selected
    assert (await settings.get("issuer|outsider", "south"))["default_agent_id"] is None
    cleared = await settings.update("issuer|admin", "north", None, 1)
    assert cleared["revision"] == 2 and cleared["status"] == "unconfigured"
    assert not cleared["can_run"]
    with pytest.raises(ConflictException):
        await settings.update("issuer|admin", "north", agent["id"], 1)


async def test_default_writes_require_organization_operator_and_global_agent(assistants):
    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository
    from koinon.catalog.service import CatalogService

    service, context = assistants
    settings = await settings_service(context)
    provider, agent = await configured(service)
    with pytest.raises(AccessDenied):
        await settings.update("issuer|viewer", "north", agent["id"], 0)
    with pytest.raises(AccessDenied):
        await settings.update("issuer|admin", "north", "missing", 0)
    with pytest.raises(AccessDenied):
        await settings.update("issuer|outsider", "south", agent["id"], 0)
    workspace = await context.get_bean(CatalogService).create(
        "issuer|admin", "north", kind="workspace", name="W"
    )
    scoped = await service.save_agent(
        "issuer|admin",
        "north",
        dict(
            name="Scoped",
            provider_id=provider["id"],
            model_id="qwen2.5:1.5b",
            scope={"workspace_id": workspace.id},
        ),
    )
    with pytest.raises(InvalidRequestException):
        await settings.update("issuer|admin", "north", scoped["id"], 0)
    await context.get_bean(MembershipRepository).save(
        Membership(
            id="scoped-operator",
            subject="issuer|scoped",
            tenant_id="north",
            workspace_id=workspace.id,
            role="operator",
        )
    )
    with pytest.raises(AccessDenied):
        await settings.update("issuer|scoped", "north", agent["id"], 0)
    with pytest.raises(AccessDenied):
        await settings.get("issuer|scoped", "north")
    assert (await settings.get("issuer|scoped", "north", workspace_id=workspace.id))["revision"] == 0


async def test_concurrent_first_selection_has_one_winner_and_disabled_default_is_not_replaced(assistants):
    service, context = assistants
    settings = await settings_service(context)
    _, agent = await configured(service)
    results = await asyncio.gather(
        *(settings.update("issuer|admin", "north", agent["id"], 0) for _ in range(2)), return_exceptions=True
    )
    assert sum(isinstance(result, dict) for result in results) == 1, results
    assert sum(isinstance(result, ConflictException) for result in results) == 1, results
    await service.save_agent("issuer|admin", "north", {"enabled": False}, agent["id"])
    current = await settings.get("issuer|viewer", "north")
    assert current["default_agent_id"] == agent["id"]
    assert current["status"] == "disabled" and current["can_run"] is False


async def test_revision_updates_are_atomic_and_persist_actor_and_audit_without_agent_secrets(assistants):
    from koinon.catalog.repositories import AuditRepository
    from koinon.organization_chat.repositories import OrganizationChatRepository

    service, context = assistants
    settings = await settings_service(context)
    _, agent = await configured(service)
    await settings.update("issuer|admin", "north", agent["id"], 0)
    results = await asyncio.gather(
        settings.update("issuer|admin", "north", None, 1),
        settings.update("issuer|admin", "north", agent["id"], 1),
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, ConflictException) for result in results) == 1
    persisted = await OrganizationChatRepository().find_by_id("north")
    assert persisted.revision == 2 and persisted.updated_by == "issuer|admin"
    assert persisted.updated_at.tzinfo is not None
    audits = await context.get_bean(AuditRepository).find_all(action="organization_chat.updated")
    assert len(audits) == 2
    assert "private-provider-key" not in str(await settings.get("issuer|viewer", "north"))
    assert "private-provider-key" not in str(audits)
