# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_index_persistence import index_rows as index_rows

from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import CatalogRepository
from koinon.knowledge.indexes.service import KnowledgeIndexService


def dependencies():
    workspace = SimpleNamespace(
        id="workspace", kind="workspace", workspace_id="workspace", tenant_id="tenant", status="ready"
    )
    facade = SimpleNamespace(
        _chain=AsyncMock(return_value=[workspace]),
        bindings=SimpleNamespace(find_all=AsyncMock(side_effect=[[SimpleNamespace()], []])),
        binding=AsyncMock(return_value=SimpleNamespace(native_id="native", native_workspace_id="native")),
        catalog=SimpleNamespace(
            restriction=None,
            authorize=AsyncMock(),
            catalog_repository=SimpleNamespace(find_by_id=AsyncMock(return_value=workspace)),
        ),
    )
    adapter = SimpleNamespace(discover=AsyncMock(return_value={"items": [], "total": 0}))
    connections = SimpleNamespace(authority=AsyncMock())
    service = KnowledgeIndexService(
        facade,
        adapter,
        connections,
        SimpleNamespace(prepare=AsyncMock()),
        SimpleNamespace(for_native_ids=AsyncMock(return_value=[])),
    )
    return service, facade, adapter, connections


async def test_foreign_or_archived_workspace_is_denied_before_native_discovery():
    service, facade, adapter, _ = dependencies()
    facade._chain.side_effect = AccessDenied("Unavailable")
    with pytest.raises(AccessDenied):
        await service.choices("actor", "tenant", workspace_id="foreign", domain="documents")
    adapter.discover.assert_not_awaited()


async def test_discovery_uses_immutable_native_binding_and_bounded_paging():
    service, facade, adapter, _ = dependencies()
    result = await service.choices(
        "actor", "tenant", workspace_id="workspace", domain="documents", limit=20, offset=4
    )
    assert result == {"items": [], "total": 0, "limit": 20, "offset": 4}
    facade.binding.assert_awaited_once()
    arguments = adapter.discover.await_args.kwargs
    assert arguments["tenant_id"] == "tenant"
    assert arguments["native_workspace_id"] == "native"
    assert arguments["catalog_workspace_id"] == "workspace"
    assert arguments["limit"] == 20 and arguments["offset"] == 4


async def test_viewer_discovery_hides_provider_ids_without_opening_provider_clients():
    service, _, adapter, connections = dependencies()
    connections.authority.side_effect = AccessDenied("No management")
    adapter.discover.return_value = {
        "items": [
            {"id": "index", "native_id": "set", "provider_id": "secret-reference", "model_id": "embedding"}
        ],
        "total": 1,
    }
    result = await service.choices("viewer", "tenant", workspace_id="workspace", domain="structured")
    assert result["items"] == [
        {"id": "index", "native_id": "set", "model_id": "embedding", "tenant_id": "tenant"}
    ]


async def test_index_management_requires_workspace_permission_and_write_resource_guard_before_native_calls():
    service, facade, adapter, _ = dependencies()
    facade.catalog.restriction = SimpleNamespace(
        resource=AsyncMock(side_effect=AccessDenied("Narrow asset token"))
    )
    with pytest.raises(AccessDenied):
        await service.authority("actor", "tenant", "workspace", write=True)
    facade.catalog.authorize.assert_awaited_once_with("actor", "tenant", "indexes:manage", "workspace")
    adapter.discover.assert_not_awaited()


async def test_standalone_plan_holds_native_read_write_unit_for_authority_locks(index_rows):
    service, facade, _, connections = dependencies()
    facade.catalog.catalog_repository = CatalogRepository()
    facade.bindings.find_all = AsyncMock(return_value=[])
    connections.selected = AsyncMock(return_value=None)
    service.planner.prepare = AsyncMock(
        return_value=(
            SimpleNamespace(kind="ollama", revision=1),
            {"dimensions": 768, "storage_dimensions": 768, "qualification": "probe_passed"},
        )
    )
    plan = await service.plan(
        "issuer|actor",
        "tenant",
        {
            "workspace_id": "workspace",
            "domain": "documents",
            "provider_id": "provider",
            "model_id": "embedding",
        },
    )
    assert plan["dimensions"] == 768 and plan["active_index_id"] is None
