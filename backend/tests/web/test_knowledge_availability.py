# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from conftest import bearer
from pyfly.container import bean, configuration
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from koinon.catalog.service import CatalogService
from koinon.knowledge.availability.adapter import NativeAvailabilityAdapter
from koinon.knowledge.availability.controller import KnowledgeAvailabilityController
from koinon.knowledge.availability.repository import AvailabilityRepository
from koinon.knowledge.availability.service import KnowledgeAvailabilityService
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings


@configuration
class AvailabilityTestBeans:
    @bean
    def availability(
        self, catalog: CatalogService, datasources: DataSourceRegistry
    ) -> KnowledgeAvailabilityService:
        facade = KnowledgeFacade(catalog, DomainBindingRepository(), None, KnowledgeSettings())
        return KnowledgeAvailabilityService(
            facade, AvailabilityRepository(), NativeAvailabilityAdapter(datasources)
        )


@pytest.fixture(autouse=True)
def register_test_ports(monkeypatch):
    from koinon import app as application

    original = application.create_application

    def create(*args, **kwargs):
        app = original(*args, **kwargs)
        app.state.context.register_bean(AvailabilityTestBeans)
        app.state.context.register_bean(KnowledgeAvailabilityController)
        return app

    monkeypatch.setattr(application, "create_application", create)


def create(client, kind, parent, name="fixture"):
    response = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer(),
        json={"kind": kind, "name": name, "parent_id": parent},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def token(client, assets):
    response = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Availability boundary",
            "tenant_id": "north",
            "scopes": ["catalog:read"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "workspace_ids": [client.workspace_id],
            "asset_ids": assets,
        },
    )
    assert response.status_code == 201, response.text
    return response.json(), {"Authorization": "Bearer " + response.json()["token"]}


def test_actual_typed_endpoint_denies_foreign_assets_and_freshly_revoked_pat(client):
    from koinon.tokens.repositories import PersonalTokenRepository

    project = create(client, "project", client.workspace_id)
    folder = create(client, "collection", project)
    source = create(client, "source", folder)
    document = create(client, "document", source)
    other = create(client, "source", folder, "other")
    credential, headers = token(client, [document])
    path = "/api/v1/tenants/north/catalog/availability"
    response = client.post(path, headers=headers, json={"asset_ids": [document]})
    assert response.status_code == 200, response.text
    assert response.json()["items"][document]["search"]["state"] == "unknown"
    assert "no-store" in response.headers["cache-control"]
    assert (
        client.post(
            path, headers=headers, json={"asset_ids": [document], "workspace_id": "foreign"}
        ).status_code
        == 403
    )
    assert client.post(path, headers=headers, json={"asset_ids": [other]}).status_code == 403
    assert (
        client.post(
            path.replace("/north/", "/south/"), headers=headers, json={"asset_ids": [document]}
        ).status_code
        == 403
    )

    async def revoke():
        repository = client.native_app.state.context.get_bean(PersonalTokenRepository)
        row = await repository.find_by_id(credential["id"])
        row.revoked_at = datetime.now(UTC)
        await repository.save(row)

    client.portal.call(revoke)
    assert client.post(path, headers=headers, json={"asset_ids": [document]}).status_code == 401


def test_native_catalog_filter_contract_and_processing_admin_authority(client):
    for status in ("pending", "error", "ready"):
        response = client.get("/api/v1/tenants/north/catalog", headers=bearer(), params={"status": status})
        assert response.status_code == 200, response.text
    assert (
        client.post(
            "/api/v1/tenants/north/knowledge-processing", headers=bearer("viewer"), json={}
        ).status_code
        == 403
    )
    response = client.post(
        "/api/v1/tenants/north/knowledge-processing", headers=bearer(), json={"page_size": 1}
    )
    assert response.status_code == 200, response.text
    assert response.json()["items"] == []
