# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from koinon.catalog.errors import AccessDenied


def fixture(pointer):
    row = SimpleNamespace(
        id="index",
        tenant_id="north",
        workspace_id="workspace",
        native_workspace_id="native-workspace",
        domain="documents",
        native_id="target",
        status="activating",
        revision=5,
        transition={"previous_native_id": "previous"},
    )
    workspace = SimpleNamespace(id="workspace")
    restriction = SimpleNamespace(resource=AsyncMock())
    catalog = SimpleNamespace(authorize=AsyncMock(), restriction=restriction)
    reader = SimpleNamespace(
        authority=AsyncMock(return_value=workspace),
        facade=SimpleNamespace(catalog=catalog),
        connections=SimpleNamespace(
            authority=AsyncMock(), selected=AsyncMock(return_value=SimpleNamespace(revision=7))
        ),
        adapter=SimpleNamespace(overview=AsyncMock(return_value={"active_native_id": pointer})),
    )
    lifecycle = SimpleNamespace(scoped=AsyncMock(return_value=row), reader=reader)
    service = import_module(
        "koinon.organization_knowledge.transitions.index_recovery"
    ).ModeIndexRecoveryService(lifecycle)
    return service, lifecycle, row


@pytest.mark.parametrize(
    "pointer,state,actions",
    [
        ("target", "target", ["finish", "restore_previous"]),
        ("previous", "previous", ["restore_previous"]),
        ("foreign", "other", []),
        (None, "other", []),
    ],
)
async def test_recovery_actions_follow_fresh_native_pointer_without_a_new_switch(pointer, state, actions):
    service, lifecycle, row = fixture(pointer)
    result = await service.inspect("admin", "north", row.id)
    assert result["native_pointer_state"] == state
    assert result["actions"] == actions
    assert result["expected_revision"] == 5 and result["expected_connection_revision"] == 7
    lifecycle.scoped.assert_awaited_once_with("admin", "north", "index")
    lifecycle.reader.adapter.overview.assert_awaited_once_with(
        tenant_id="north", workspace_id="native-workspace", domain="documents", actor="admin"
    )
    lifecycle.reader.facade.catalog.authorize.assert_awaited_once_with(
        "admin", "north", "indexes:manage", "workspace"
    )
    lifecycle.reader.facade.catalog.restriction.resource.assert_awaited_once_with(
        "admin", lifecycle.reader.authority.return_value, write=True
    )


async def test_recovery_inspection_does_not_read_native_state_after_permission_revocation():
    service, lifecycle, row = fixture("target")
    lifecycle.reader.facade.catalog.authorize.side_effect = AccessDenied("revoked", code="ACCESS_DENIED")
    with pytest.raises(AccessDenied):
        await service.inspect("admin", "north", row.id)
    lifecycle.reader.adapter.overview.assert_not_awaited()


async def test_native_observation_failure_is_not_a_recovery_action():
    service, lifecycle, row = fixture("target")
    lifecycle.reader.adapter.overview.side_effect = RuntimeError("native unavailable")
    result = await service.inspect("admin", "north", row.id)
    assert result["native_pointer_state"] == "unavailable" and result["actions"] == []
