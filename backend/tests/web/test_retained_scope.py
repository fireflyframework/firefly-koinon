# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import uuid4

import pytest
from conftest import bearer
from pyfly.data.relational.sqlalchemy import SessionProvider
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

pytest.importorskip("flyquery")
from flyquery.core.services.datasets.dataset_repository import DatasetRepository
from flyquery.core.services.datasets.dataset_service import DatasetService
from flyquery.web.controllers.datasets_controller import DatasetsController


@pytest.mark.parametrize("client", [(DatasetsController, "structured")], indirect=True)
def test_own_headers_cannot_expose_an_actual_stored_retained_victim(client):
    context = client.native_app.state.context
    victim = str(uuid4())

    async def persist_victim():
        async with context.get_bean(SessionProvider).unit() as session:
            await session.execute(
                text(
                    "CREATE TABLE flyquery_datasets (id TEXT PRIMARY KEY, tenant_id TEXT, "
                    "workspace_id TEXT, name TEXT)"
                )
            )
            await session.execute(
                text("INSERT INTO flyquery_datasets VALUES (:id, :tenant, :workspace, :name)"),
                {
                    "id": victim,
                    "tenant": "south",
                    "workspace": str(uuid4()),
                    "name": "Victim private dataset",
                },
            )
        service = DatasetService(DatasetRepository(context.get_bean(async_sessionmaker)))
        row = await service.get(victim)
        assert row["tenant_id"] == "south"
        return row

    # Establish the actual retained unscoped get() can fetch this persisted other-tenant row.
    assert client.portal.call(persist_victim)["name"] == "Victim private dataset"
    response = client.get(
        "/api/v1/structured/datasets/" + victim,
        headers={
            **bearer(),
            "X-Tenant-Id": "north",
            "X-Workspace-Id": client.workspace_id,
            "X-Agent-Token": "legacy-token-must-not-bypass",
        },
    )
    assert response.status_code == 503
    assert response.json()["code"] == "LEGACY_OPERATION_UNQUALIFIED"
    assert "Victim private dataset" not in response.text
