# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request
from test_facade import context as context
from test_facade import upload


def admission(facade, enabled=True):
    from koinon.knowledge.legacy_read import LegacyReadAdmission
    from koinon.web.legacy_security import LegacyOperationPolicies

    policies = LegacyOperationPolicies()
    capabilities = SimpleNamespace(domains={key: {"registered": enabled} for key in ("canon", "structured")})
    value = LegacyReadAdmission(facade, SimpleNamespace(), policies, capabilities)
    return value, policies


def request(query=b""):
    return Request(
        {"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": query, "state": {}}
    )


async def test_only_explicit_read_operations_are_registered_and_disabled_domains_stay_gated(context):
    from koinon.knowledge.legacy_read import READ_OPERATIONS

    facade, _, _, _, _ = context
    _, policies = admission(facade)
    assert len(policies.operations) == len(READ_OPERATIONS) == 94
    assert policies.resolve("GET", "/api/v1/canon/sources/source")
    assert policies.resolve("GET", "/api/v1/structured/tables/table")
    assert policies.resolve("POST", "/api/v1/canon/sources") is None
    assert policies.resolve("GET", "/api/v1/structured/agent-tokens") is None
    assert policies.resolve("GET", "/api/v1/canon/workspaces") is None
    assert not admission(facade, enabled=False)[1].operations


async def test_canonical_archive_and_foreign_tenant_are_denied_before_retained_lookup(context):
    from koinon.catalog.errors import AccessDenied

    facade, catalog, _, tree, _ = context
    await upload(context)
    guard, _ = admission(facade)
    guard._lookup = AsyncMock(
        return_value={"id": "native-source", "tenant_id": "north", "workspace_id": "native-workspace"}
    )
    with pytest.raises(AccessDenied):
        await guard.verify(
            "canon",
            request(),
            SimpleNamespace(subject="issuer|outsider"),
            "north",
            tree["workspace"].id,
            {"source_id": "native-source"},
        )
    guard._lookup.assert_not_awaited()
    await catalog.archive("issuer|admin", "north", tree["collection"].id)
    with pytest.raises(AccessDenied, match="archived"):
        await guard.verify(
            "canon",
            request(),
            SimpleNamespace(subject="issuer|reader"),
            "north",
            tree["workspace"].id,
            {"source_id": "native-source"},
        )
    guard._lookup.assert_not_awaited()


async def test_asset_restricted_tokens_cannot_read_broad_or_unbound_retained_resources(context):
    from koinon.catalog.errors import AccessDenied

    facade, catalog, _, tree, _ = context
    await upload(context)
    catalog.restriction = SimpleNamespace(
        grant=AsyncMock(
            return_value=SimpleNamespace(
                tenant_id="north",
                workspace_ids=[tree["workspace"].id],
                asset_ids=["selected"],
                scopes=["catalog:read"],
            )
        ),
        resource=AsyncMock(),
    )
    guard, _ = admission(facade)
    guard._lookup = AsyncMock(
        return_value={"id": "unbound", "tenant_id": "north", "workspace_id": "native-workspace"}
    )
    with pytest.raises(AccessDenied, match="asset"):
        await guard.verify(
            "canon", request(), SimpleNamespace(subject="issuer|reader"), "north", tree["workspace"].id, {}
        )
    guard._lookup.assert_not_awaited()
    with pytest.raises(AccessDenied, match="asset"):
        await guard.verify(
            "canon",
            request(),
            SimpleNamespace(subject="issuer|reader"),
            "north",
            tree["workspace"].id,
            {"item_id": "unbound"},
        )
    guard._lookup.return_value = {
        "id": "native-source",
        "tenant_id": "north",
        "workspace_id": "native-workspace",
    }
    await guard.verify(
        "canon",
        request(),
        SimpleNamespace(subject="issuer|reader"),
        "north",
        tree["workspace"].id,
        {"source_id": "native-source"},
    )


async def test_admitted_source_uses_binding_workspace_and_trusted_actor(context):
    from flycanon.web.conventions.context import current_tenant_context

    facade, _, _, tree, _ = context
    await upload(context)
    guard, _ = admission(facade)

    async def lookup(domain, kind, identifier, tenant, workspace):
        context = current_tenant_context()
        assert context.actor == "issuer|reader" and context.workspace_id == "native-workspace"
        assert workspace == "native-workspace"
        return {"id": "native-source", "tenant_id": "north", "workspace_id": workspace}

    guard._lookup = AsyncMock(side_effect=lookup)
    value = request()
    await guard.verify(
        "canon",
        value,
        SimpleNamespace(subject="issuer|reader"),
        "north",
        tree["workspace"].id,
        {"source_id": "native-source"},
    )
    assert value.state.verified_native_workspace_id == "native-workspace"
    assert current_tenant_context() is None


async def test_deduplicated_source_remains_readable_through_an_active_authorized_alias(context):
    facade, catalog, _, tree, _ = context
    first = await upload(context)
    other = await catalog.create(
        "issuer|admin", "north", kind="collection", name="other", parent_id=tree["project"].id
    )
    await facade.upload(
        "issuer|admin",
        "north",
        workspace_id=tree["workspace"].id,
        project_id=tree["project"].id,
        parent_id=other.id,
        mode="document",
        filename="alias.txt",
        content=b"same native content",
    )
    await catalog.archive("issuer|admin", "north", first["source"]["id"])
    guard, _ = admission(facade)
    guard._lookup = AsyncMock(
        return_value={"id": "native-source", "tenant_id": "north", "workspace_id": "native-workspace"}
    )
    await guard.verify(
        "canon",
        request(),
        SimpleNamespace(subject="issuer|reader"),
        "north",
        tree["workspace"].id,
        {"source_id": "native-source"},
    )
    guard._lookup.assert_awaited_once()


async def test_parent_dataset_mismatch_and_foreign_rows_are_refused(context):
    from koinon.catalog.errors import AccessDenied

    facade, _, _, tree, _ = context
    guard, _ = admission(facade)
    workspace = tree["workspace"].id
    guard._lookup = AsyncMock(
        side_effect=lambda domain, kind, identifier, tenant, native_workspace: {
            "id": identifier,
            "tenant_id": tenant,
            "workspace_id": native_workspace,
            **({"dataset_id": "other"} if kind == "table" else {}),
        }
    )
    with pytest.raises(AccessDenied, match="ancestor"):
        await guard.verify(
            "structured",
            request(),
            SimpleNamespace(subject="issuer|reader"),
            "north",
            workspace,
            {"dataset_id": "selected", "table_id": "table"},
        )
    guard._lookup = AsyncMock(return_value={"id": "table", "tenant_id": "south", "workspace_id": workspace})
    with pytest.raises(AccessDenied):
        await guard.verify(
            "structured",
            request(),
            SimpleNamespace(subject="issuer|reader"),
            "north",
            workspace,
            {"table_id": "table"},
        )


async def test_child_table_dataset_and_query_scope_are_all_checked(context):
    from koinon.catalog.errors import AccessDenied

    facade, _, _, tree, _ = context
    guard, _ = admission(facade)
    workspace = tree["workspace"].id
    rows = {
        ("object", "object"): {"table_id": "table", "snapshot_id": "snapshot"},
        ("table", "table"): {"dataset_id": "dataset"},
        ("snapshot", "snapshot"): {"table_id": "table", "dataset_id": "dataset"},
        ("dataset", "dataset"): {},
    }
    guard._lookup = AsyncMock(
        side_effect=lambda domain, kind, identifier, tenant, native_workspace: {
            "id": identifier,
            "tenant_id": tenant,
            "workspace_id": native_workspace,
            **rows[kind, identifier],
        }
    )
    await guard.verify(
        "structured",
        request(),
        SimpleNamespace(subject="issuer|reader"),
        "north",
        workspace,
        {"object_id": "object"},
    )
    assert {call.args[1] for call in guard._lookup.await_args_list} == {
        "object",
        "table",
        "snapshot",
        "dataset",
    }
    guard._lookup.reset_mock()
    with pytest.raises(AccessDenied):
        await guard.verify(
            "structured",
            request(b"workspace_id=foreign"),
            SimpleNamespace(subject="issuer|reader"),
            "north",
            workspace,
            {},
        )
    guard._lookup.assert_not_awaited()
