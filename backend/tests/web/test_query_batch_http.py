# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import socket
from types import SimpleNamespace
from uuid import uuid4

import pytest
from conftest import ISSUER, bearer


@pytest.fixture(autouse=True)
def native_query_slice(monkeypatch):
    from pyfly.container.scanner import scan_package

    import koinon.app
    from koinon.knowledge.bulk_queries.controllers import QueryBatchController
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.web.projection import register_controller

    original = koinon.app.create_application

    def compose(config):
        app = original(config)
        for package in ["koinon.knowledge.bulk", "koinon.knowledge.bulk_queries"]:
            scan_package(package, app.state.context.container)
        app.state.context.register_bean(KnowledgeConnectionRepository)
        app.state.context.register_bean(DomainBindingRepository)
        register_controller(app.state.context, QueryBatchController)
        return app

    def denied(*_, **__):
        raise AssertionError("No actual socket/listener/model/provider in native query HTTP qualification")

    monkeypatch.setattr(koinon.app, "create_application", compose)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "listen", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def test_native_query_routes_bind_current_actor_and_private_outcomes_without_any_model(client):
    from koinon.assistants.entities import Provider
    from koinon.assistants.repositories import ProviderRepository
    from koinon.catalog.service import CatalogService
    from koinon.knowledge.bulk_queries.authority import QueryBatchAuthority
    from koinon.knowledge.connections.entities import KnowledgeConnection
    from koinon.knowledge.connections.repositories import KnowledgeConnectionRepository
    from koinon.knowledge.entities import DomainBinding
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings
    from koinon.organization_knowledge.service import OrganizationKnowledgeService

    async def prepare():
        context = client.native_app.state.context
        catalog = context.get_bean(CatalogService)
        bindings = context.get_bean(DomainBindingRepository)
        subject = ISSUER + "|admin"
        project = await catalog.create(
            subject, "north", kind="project", name="Project", parent_id=client.workspace_id
        )
        parent = await catalog.create(
            subject, "north", kind="collection", name="Collection", parent_id=project.id
        )
        source = await catalog.create(subject, "north", kind="source", name="Source", parent_id=parent.id)
        dataset = await catalog.create(subject, "north", kind="dataset", name="Dataset", parent_id=source.id)
        native_workspace = str(uuid4())
        for entry, kind, native in [
            (client.workspace_id, "workspace", native_workspace),
            (dataset.id, "dataset", str(uuid4())),
        ]:
            await bindings.save(
                DomainBinding(
                    id=str(uuid4()),
                    tenant_id="north",
                    catalog_id=entry,
                    workspace_id=client.workspace_id,
                    domain="structured",
                    entity_kind=kind,
                    native_id=native,
                    native_workspace_id=native_workspace,
                    created_by=subject,
                )
            )
        await context.get_bean(ProviderRepository).save(
            Provider(
                id="inert",
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
        for role in ["embedding", "grounding", "generation", "critic", "explainer"]:
            await context.get_bean(KnowledgeConnectionRepository).save(
                KnowledgeConnection(
                    id=role,
                    tenant_id="north",
                    workspace_id=client.workspace_id,
                    scope_key=client.workspace_id,
                    domain="structured",
                    role="structured." + role,
                    mode="provider",
                    provider_id="inert",
                    model_id="model",
                    dimensions=768,
                    embedding_fingerprint="a" * 64,
                    created_by=subject,
                    updated_by=subject,
                )
            )
        facade = KnowledgeFacade(
            catalog,
            bindings,
            SimpleNamespace(),
            KnowledgeSettings(),
            knowledge_settings=context.get_bean(OrganizationKnowledgeService),
        )
        context.get_bean(QueryBatchAuthority).facades = SimpleNamespace(get=lambda: facade)
        return dataset.id

    dataset_id = client.portal.call(prepare)
    path = "/api/v1/tenants/north/queries/batches"
    body = {
        "workspace_id": client.workspace_id,
        "items": [{"client_item_id": "one", "dataset_id": dataset_id, "question": "Count"}],
    }
    assert client.post(path, headers=bearer("analyst"), json=body).status_code in [400, 422]
    created = client.post(path, headers={**bearer("analyst"), "Idempotency-Key": "create"}, json=body)
    assert created.status_code == 201, created.text
    batch = created.json()
    assert created.headers["cache-control"] == "private, no-store"
    assert client.get(path, headers=bearer("analyst")).json()["total"] == 1
    assert client.get(path, headers=bearer("editor")).json()["total"] == 0
    assert client.get(path + "/" + batch["id"], headers=bearer("editor")).status_code == 403
    items = client.get(path + "/" + batch["id"] + "/items", headers=bearer("analyst")).json()["items"]
    result = client.get(
        path + "/" + batch["id"] + "/items/" + items[0]["id"] + "/result", headers=bearer("analyst")
    )
    assert result.status_code == 200 and result.json()["result"] is None
    cancelled = client.post(
        path + "/" + batch["id"] + "/cancel",
        headers={**bearer("analyst"), "Idempotency-Key": "cancel"},
        json={"expected_revision": batch["revision"]},
    )
    assert cancelled.status_code == 200 and cancelled.json()["cancellation_requested"] is True
    assert "question" not in cancelled.text and "items" not in cancelled.text
