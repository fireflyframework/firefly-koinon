# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from test_query_native_repository import policy

from koinon.assistants.entities import Provider
from koinon.assistants.repositories import ProviderRepository
from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.knowledge.bulk_queries.authority import QueryBatchAuthority
from koinon.knowledge.connections.entities import KnowledgeConnection
from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.repositories import PersonalTokenRepository


@pytest.fixture
async def queries(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'queries.db'}",
                        }
                    },
                }
            }
        )
    )
    for package in [
        "koinon.catalog",
        "koinon.jobs",
        "koinon.knowledge.bulk",
        "koinon.knowledge.bulk_queries",
    ]:
        scan_package(package, context.container)
    for bean in [
        PersonalTokenRepository,
        TokenRestriction,
        ProviderRepository,
        KnowledgeConnectionRepository,
        DomainBindingRepository,
    ]:
        context.register_bean(bean)
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        members = context.get_bean(MembershipRepository)
        for subject, role in [
            ("issuer|admin", "admin"),
            ("issuer|analyst", "analyst"),
            ("issuer|other", "analyst"),
        ]:
            await members.save(Membership(id=subject, subject=subject, tenant_id="north", role=role))
        catalog = context.get_bean(CatalogService)
        workspace = await catalog.create("issuer|admin", "north", kind="workspace", name="Workspace")
        project = await catalog.create(
            "issuer|admin", "north", kind="project", name="Project", parent_id=workspace.id
        )
        parent = await catalog.create(
            "issuer|admin", "north", kind="collection", name="Collection", parent_id=project.id
        )
        source = await catalog.create(
            "issuer|admin", "north", kind="source", name="Source", parent_id=parent.id
        )
        dataset = await catalog.create(
            "issuer|admin", "north", kind="dataset", name="Dataset", parent_id=source.id
        )
        bindings = context.get_bean(DomainBindingRepository)
        native_workspace, native_dataset = str(uuid4()), str(uuid4())
        for entry, native in [(workspace, native_workspace), (dataset, native_dataset)]:
            await bindings.save(
                DomainBinding(
                    id=str(uuid4()),
                    tenant_id="north",
                    catalog_id=entry.id,
                    workspace_id=workspace.id,
                    domain="structured",
                    entity_kind=entry.kind,
                    native_id=native,
                    native_workspace_id=native_workspace,
                    created_by="issuer|admin",
                )
            )
        await context.get_bean(ProviderRepository).save(
            Provider(
                id="model-provider",
                tenant_id="north",
                name="Inert",
                kind="ollama",
                base_url="http://unresolved.invalid",
                model_ids=["model"],
                enabled=True,
                revision=1,
                validated_revision=1,
            )
        )
        connections = context.get_bean(KnowledgeConnectionRepository)
        for role in [
            "structured.embedding",
            "structured.grounding",
            "structured.generation",
            "structured.explainer",
            "structured.critic",
        ]:
            await connections.save(
                KnowledgeConnection(
                    id=role,
                    tenant_id="north",
                    workspace_id=workspace.id,
                    scope_key=workspace.id,
                    domain="structured",
                    role=role,
                    mode="provider",
                    provider_id="model-provider",
                    model_id="model",
                    dimensions=768 if role.endswith("embedding") else None,
                    embedding_fingerprint="a" * 64 if role.endswith("embedding") else None,
                    created_by="issuer|admin",
                    updated_by="issuer|admin",
                )
            )
        facade = KnowledgeFacade(
            catalog,
            bindings,
            SimpleNamespace(),
            KnowledgeSettings(),
            knowledge_settings=SimpleNamespace(snapshot=AsyncMock(return_value=policy())),
        )
        context.get_bean(QueryBatchAuthority).facades = SimpleNamespace(get=lambda: facade)
        yield SimpleNamespace(
            context=context,
            catalog=catalog,
            members=members,
            workspace=workspace,
            dataset=dataset,
            facade=facade,
            bindings=bindings,
            connections=connections,
            target={"workspace_id": workspace.id, "dataset_id": dataset.id},
        )
    finally:
        await context.stop()
