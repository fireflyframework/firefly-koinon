# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Dependency diagnostics describe authorized assignments without invoking a provider."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from flycanon.config import CanonSettings
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from sqlalchemy import update
from test_knowledge_connections import configured as configured

from koinon.assistants.configuration_service import AssistantConfigurationService
from koinon.assistants.connections import ConnectionResolver
from koinon.assistants.dependencies import ConnectionDependencies
from koinon.assistants.repositories import ProviderRepository
from koinon.assistants.scope import KnowledgeScopePolicy
from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied


@pytest.fixture
async def diagnostics(configured, monkeypatch):
    connections, _, _, tree, context = configured
    workspace = tree["workspace"].id
    context.container.register_instance(
        CanonSettings, CanonSettings(embedding_model="openai:text-embedding-3-small")
    )
    row = SimpleNamespace(
        id="agent",
        tenant_id="north",
        name="Scoped agent",
        description="",
        provider_id="north-provider",
        model_id="qwen2.5:3b",
        model_options={},
        tools=["search_knowledge"],
        scope={},
        instructions="",
        enabled=True,
        revision=1,
    )
    dependencies = ConnectionDependencies(context.container, context.get_bean(DataSourceRegistry))
    dependencies.knowledge_connections = connections
    service = AssistantConfigurationService(
        catalog=connections.catalog,
        providers=context.get_bean(ProviderRepository),
        agents=SimpleNamespace(find_all=AsyncMock(return_value=[row])),
        secrets=None,
        settings=None,
        probe=None,
        scope_policy=KnowledgeScopePolicy(connections.catalog),
        connections=context.get_bean(ConnectionResolver),
        dependencies=dependencies,
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Diagnostics must not create model clients or retrieve credentials")

    monkeypatch.setattr(connections.compiler.models, "build", forbidden)

    async def assign(**changes):
        return await connections.save(
            "issuer|admin",
            "north",
            {
                "domain": "documents",
                "role": "documents.embedding",
                "workspace_id": workspace,
                "mode": "provider",
                "provider_id": "north-provider",
                "model_id": "nomic-embed-text",
                "dimensions": 768,
                "storage_dimensions": 768,
                "space_id": "private-test-space",
                **changes,
            },
        )

    async def show(subject="issuer|admin", selected_workspace=workspace):
        agents = await service.list_agents(
            subject, "north", scope={"workspace_id": selected_workspace} if selected_workspace else None
        )
        return agents[0]["dependencies"]

    return SimpleNamespace(
        service=service,
        connections=connections,
        context=context,
        workspace=workspace,
        row=row,
        assign=assign,
        show=show,
    )


async def test_scoped_embedding_matches_persisted_assignment(diagnostics):
    d = diagnostics
    assignment = await d.assign()
    selected = await d.connections.selected("north", d.workspace, "documents", "documents.embedding")
    assert selected.id == assignment["id"]
    dependency = (await d.show())[0]
    assert dependency["provider"] == "ollama"
    assert dependency["model_id"] == selected.model_id == "nomic-embed-text"
    assert dependency["ownership"] == "deployment"  # Stable SDK vocabulary for read-only diagnostics.
    assert "workspace" in dependency["reason"].lower()
    assert dependency["available"] is None and dependency["status"] == "unverified"


async def test_no_workspace_never_reads_or_displays_unadmitted_roles(diagnostics, monkeypatch):
    await diagnostics.assign(workspace_id=None)
    selected = AsyncMock(side_effect=AssertionError("An absent workspace cannot resolve role assignments"))
    monkeypatch.setattr(diagnostics.connections, "selected", selected)
    dependency = (await diagnostics.show(selected_workspace=None))[0]
    assert dependency["provider"] is None and dependency["model_id"] is None
    assert dependency["available"] is None and "workspace" in dependency["reason"].lower()
    selected.assert_not_called()


async def test_disabled_workspace_assignment_does_not_fall_back_to_tenant(diagnostics):
    await diagnostics.assign(workspace_id=None)
    await diagnostics.assign(enabled=False)
    dependency = (await diagnostics.show())[0]
    assert dependency["configured"] is False and dependency["status"] == "needs_setup"
    assert "workspace" in dependency["reason"].lower() and "disabled" in dependency["reason"].lower()


async def test_provider_read_permission_is_required_for_dependency_details(diagnostics, monkeypatch):
    await diagnostics.assign()
    selected = AsyncMock(side_effect=AssertionError("Denied readers must not inspect role assignments"))
    monkeypatch.setattr(diagnostics.connections, "selected", selected)
    dependency = (await diagnostics.show(subject="issuer|reader"))[0]
    assert dependency["provider"] is None and dependency["model_id"] is None
    assert dependency["available"] is None
    selected.assert_not_called()


async def test_foreign_workspace_is_rejected_before_dependency_lookup(diagnostics, monkeypatch):
    selected = AsyncMock(side_effect=AssertionError("A foreign actor cannot inspect role assignments"))
    monkeypatch.setattr(diagnostics.connections, "selected", selected)
    with pytest.raises(AccessDenied):
        await diagnostics.show(subject="issuer|outsider")
    selected.assert_not_called()


async def test_current_agent_is_explicit_and_never_a_deployment_default(diagnostics):
    d = diagnostics
    d.row.tools = ["query_dataset"]
    await d.assign(
        domain="structured",
        role="structured.grounding",
        mode="current_agent",
        provider_id=None,
        model_id=None,
        dimensions=None,
        storage_dimensions=None,
        space_id=None,
    )
    dependencies = await d.show()
    grounding = next(row for row in dependencies if row["id"] == "structured.grounding")
    assert grounding["provider"] == "ollama" and grounding["model_id"] == "qwen2.5:3b"
    assert "current-agent" in grounding["reason"].lower() and grounding["available"] is None
    assert all(row["model_id"] is None for row in dependencies if row["id"] == "structured.critic")


async def test_permission_revoked_during_role_lookup_hides_all_dependency_details(diagnostics, monkeypatch):
    d = diagnostics
    await d.assign()
    original = d.connections.selected

    async def revoke(*args, **kwargs):
        row = await original(*args, **kwargs)
        async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
            await connection.execute(
                update(Membership).where(Membership.subject == "issuer|admin").values(active=False)
            )
        return row

    monkeypatch.setattr(d.connections, "selected", revoke)
    dependency = (await d.show())[0]
    assert dependency["provider"] is None and dependency["model_id"] is None


async def test_native_container_injects_the_managed_connection_service(diagnostics):
    d = diagnostics
    d.context.container.register(ConnectionDependencies)
    resolved = d.context.get_bean(ConnectionDependencies)
    assert resolved.knowledge_connections is d.connections


async def test_deployment_panel_describes_defaults_as_defaults(diagnostics):
    row = next(
        row for row in diagnostics.service.dependencies.describe() if row["id"] == "documents.embedding"
    )
    assert "default" in row["reason"].lower()


async def test_tenant_assignment_is_reported_only_inside_an_admitted_workspace(diagnostics):
    await diagnostics.assign(workspace_id=None)
    dependency = (await diagnostics.show())[0]
    assert dependency["model_id"] == "nomic-embed-text"
    assert dependency["reason"].startswith("Tenant knowledge assignment")


async def test_disabled_provider_is_not_replaced_by_a_native_default(diagnostics):
    d = diagnostics
    await d.assign()
    providers = d.context.get_bean(ProviderRepository)
    provider = (await providers.find_all(tenant_id="north", id="north-provider"))[0]
    provider.enabled = False
    await providers.save(provider)
    dependency = (await d.show())[0]
    assert dependency["provider"] == "ollama" and dependency["model_id"] == "nomic-embed-text"
    assert dependency["configured"] is False and dependency["status"] == "needs_setup"
    assert dependency["available"] is None


async def test_revocation_during_a_later_role_hides_earlier_role_metadata(diagnostics, monkeypatch):
    d = diagnostics
    d.row.tools = ["query_dataset"]
    for role in ("structured.grounding", "structured.generation"):
        await d.assign(
            domain="structured",
            role=role,
            model_id="qwen2.5:3b",
            dimensions=None,
            storage_dimensions=None,
            space_id=None,
        )
    original = d.connections.selected

    async def revoke(tenant, workspace, domain, role):
        row = await original(tenant, workspace, domain, role)
        if role == "structured.generation":
            async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
                await connection.execute(
                    update(Membership).where(Membership.subject == "issuer|admin").values(active=False)
                )
        return row

    monkeypatch.setattr(d.connections, "selected", revoke)
    dependencies = await d.show()
    assert all(
        row.get("provider") is None and row.get("model_id") is None
        for row in dependencies
        if not row["id"].endswith(".datasource")
    )
