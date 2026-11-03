# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Nested folders retain exact destination identity and complete current authority."""

from datetime import timedelta

import pytest
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import update
from test_bulk_native import bulk as bulk
from test_bulk_native import request
from test_bulk_queue import queued

from koinon.catalog.ancestry import MAX_FOLDER_ANCESTRY
from koinon.catalog.entities import CatalogEntry, Tenant
from koinon.catalog.errors import AccessDenied, InvalidHierarchy
from koinon.knowledge.bulk.dtos import BulkDestination
from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.queue import BulkQueue
from koinon.security.authority import primary_authority
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository


async def nested(bulk, *, depth=2):
    ancestor = bulk.target["parent_id"]
    for index in range(depth):
        folder = await bulk.catalog.create(
            "issuer|editor", "north", kind="collection", name=f"Nested {index}", parent_id=ancestor
        )
        ancestor = folder.id
    return bulk.target | {"parent_id": ancestor}


@pytest.mark.parametrize("mode", ["document", "dataset"])
async def test_nested_batch_preserves_selected_parent_and_is_readable(bulk, mode):
    target = await nested(bulk)
    payload = request(target)
    payload = payload.model_copy(update={"items": [payload.items[0].model_copy(update={"mode": mode})]})
    batch = await bulk.service.create("issuer|editor", "north", payload, "nested")
    assert batch.destination.parent_id == target["parent_id"]
    item = (await bulk.service.items("issuer|editor", "north", batch.id)).items[0]
    source = await bulk.catalog.get("issuer|editor", "north", item.source_id)
    assert source.parent_id == target["parent_id"]
    assert source.project_id == target["project_id"]
    assert (await bulk.service.get("issuer|editor", "north", batch.id)).id == batch.id


async def test_deepest_existing_library_folder_accepts_ingestion(bulk):
    # Existing direct folder has a three-node path (folder, project, workspace).
    target = await nested(bulk, depth=MAX_FOLDER_ANCESTRY - 3)
    result = await bulk.service.create("issuer|editor", "north", request(target), "deepest")
    assert result.destination.parent_id == target["parent_id"]
    page = await bulk.service.list("issuer|editor", "north")
    assert page.total == 1 and page.items[0].id == result.id


async def test_overdeep_existing_path_is_denied_in_authority_and_history(bulk):
    target = await nested(bulk, depth=MAX_FOLDER_ANCESTRY - 3)
    batch = await bulk.service.create("issuer|editor", "north", request(target), "before-depth-change")
    extra = await bulk.catalog.create(
        "issuer|editor", "north", kind="collection", name="Extra", parent_id=target["project_id"]
    )
    async with primary_authority(read_only=False):
        await bulk.service.records._require_session().execute(
            update(CatalogEntry).where(CatalogEntry.id == bulk.target["parent_id"]).values(parent_id=extra.id)
        )
    with pytest.raises(AccessDenied):
        await bulk.service.get("issuer|editor", "north", batch.id)
    page = await bulk.service.list("issuer|editor", "north")
    assert page.total == 0 and page.items == []


@pytest.mark.parametrize("damage", ["archive", "cycle", "project", "workspace", "kind", "tenant"])
async def test_invalid_intermediate_ancestor_cannot_admit_nested_batch(bulk, damage):
    target = await nested(bulk)
    values = {
        "archive": {"status": "archived"},
        "cycle": {"parent_id": target["parent_id"]},
        "project": {"project_id": "wrong-project"},
        "workspace": {"workspace_id": "wrong-workspace"},
        "kind": {"kind": "source"},
        "tenant": {"tenant_id": "other-tenant"},
    }[damage]
    async with primary_authority(read_only=False):
        if damage == "tenant":
            bulk.service.records._require_session().add(Tenant(id="other-tenant", name="Other"))
            await bulk.service.records.flush()
        await bulk.service.records._require_session().execute(
            update(CatalogEntry).where(CatalogEntry.id == bulk.target["parent_id"]).values(**values)
        )
    with pytest.raises((AccessDenied, InvalidHierarchy)):
        await bulk.service.create("issuer|editor", "north", request(target), "bad-ancestry")


async def test_worker_rechecks_archived_intermediate_ancestor_before_publication(bulk):
    target = await nested(bulk)
    old = bulk.target
    bulk.target = target
    await queued(bulk, "nested-worker")
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("worker")
    await queue.check(lease)
    await bulk.catalog.archive("issuer|editor", "north", old["parent_id"])
    with pytest.raises((AccessDenied, InvalidHierarchy)):
        async with queue.publication(lease):
            pytest.fail("Archived ancestor reached native publication")


async def test_expected_project_mismatch_cannot_retarget_nested_folder(bulk):
    target = await nested(bulk)
    with pytest.raises((AccessDenied, InvalidHierarchy)):
        async with primary_authority(read_only=False):
            await bulk.service.authority.destination(
                "issuer|editor",
                "north",
                BulkDestination(**(target | {"project_id": "unknown-project"})),
                write=True,
            )


async def test_nested_subtree_token_can_navigate_ancestors_without_gaining_ancestor_write(bulk):
    target = await nested(bulk, depth=1)
    repository = bulk.context.get_bean(PersonalTokenRepository)
    token = PersonalToken(
        id="nested-pat",
        subject="issuer|editor",
        tenant_id="north",
        name="Inert",
        token_hash="f" * 64,
        prefix="test",
        scopes=["catalog:read", "catalog:write", "ingest:write"],
        workspace_ids=[target["workspace_id"]],
        asset_ids=[target["parent_id"]],
        resource_ids=list(bulk.target.values()),
        expires_at=now() + timedelta(hours=1),
    )
    await repository.save(token)
    with SecurityContextHolder.using(
        SecurityContext(user_id="issuer|editor", attributes={"koinon_token_id": token.id})
    ):
        result = await bulk.service.create("issuer|editor", "north", request(target), "scoped-nested")
        assert result.destination.parent_id == target["parent_id"]
        page = await bulk.service.list("issuer|editor", "north")
        assert page.total == 1 and page.items[0].id == result.id
        with pytest.raises(AccessDenied):
            await bulk.service.create("issuer|editor", "north", request(bulk.target), "outside-subtree")


async def test_nested_batch_history_filters_active_ancestry_before_count_and_page(bulk):
    target = await nested(bulk)
    first = await bulk.service.create("issuer|editor", "north", request(target), "nested-history")
    direct = await bulk.service.create("issuer|editor", "north", request(bulk.target), "direct-history")
    page = await bulk.service.list("issuer|editor", "north", page=2, page_size=1)
    assert page.total == 2 and [row.id for row in page.items] == [first.id]
    folder = await bulk.catalog.get("issuer|editor", "north", target["parent_id"])
    await bulk.catalog.archive("issuer|editor", "north", folder.parent_id)
    page = await bulk.service.list("issuer|editor", "north", page_size=1)
    assert page.total == 1 and [row.id for row in page.items] == [direct.id]


@pytest.mark.parametrize("damage", ["cycle", "project", "workspace", "kind", "tenant"])
async def test_corrupted_intermediate_ancestry_is_excluded_before_history_total(bulk, damage):
    target = await nested(bulk)
    await bulk.service.create("issuer|editor", "north", request(target), "history-corruption")
    values = {
        "cycle": {"parent_id": target["parent_id"]},
        "project": {"project_id": "wrong-project"},
        "workspace": {"workspace_id": "wrong-workspace"},
        "kind": {"kind": "source"},
        "tenant": {"tenant_id": "other-tenant"},
    }[damage]
    async with primary_authority(read_only=False):
        if damage == "tenant":
            bulk.service.records._require_session().add(Tenant(id="other-tenant", name="Other"))
            await bulk.service.records.flush()
        await bulk.service.records._require_session().execute(
            update(CatalogEntry).where(CatalogEntry.id == bulk.target["parent_id"]).values(**values)
        )
    result = await bulk.service.list("issuer|editor", "north")
    assert result.total == 0 and result.items == []


async def test_recovery_rechecks_nested_ancestor_before_native_inspection(bulk):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    original = dict(bulk.target)
    bulk.target = await nested(bulk)
    batch_id, item_id = await queued(bulk, "nested-recovery")
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("failed-worker")
    await queue.failed(lease, code="INGEST_EXECUTION_CONTEXT_REQUIRED", unknown=True)
    native = SimpleNamespace(inspect=AsyncMock())
    bulk.service.intakes = SimpleNamespace(get=lambda: native)
    await bulk.catalog.archive("issuer|editor", "north", original["parent_id"])
    with pytest.raises((AccessDenied, InvalidHierarchy)):
        await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    native.inspect.assert_not_awaited()


async def test_denied_nested_worker_preserves_policy_error_and_never_starts_native_work(bulk):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.knowledge.bulk.execution import BulkExecutor

    original = dict(bulk.target)
    bulk.target = await nested(bulk)
    batch_id, item_id = await queued(bulk, "policy-denied")
    queue = bulk.context.get_bean(BulkQueue)
    lease = await queue.claim("policy-worker")
    await bulk.catalog.archive("issuer|editor", "north", original["parent_id"])
    with pytest.raises(AccessDenied) as rejected:
        await queue.check(lease)
    assert rejected.value.code == "ACCESS_DENIED"
    native = SimpleNamespace(reserve=AsyncMock(), inspect=AsyncMock(), execute=AsyncMock())
    await BulkExecutor(queue, bulk.service.storage, SimpleNamespace(get=lambda: native)).execute(lease)
    native.reserve.assert_not_awaited()
    native.inspect.assert_not_awaited()
    native.execute.assert_not_awaited()
    item = await bulk.service.records.item(batch_id, item_id)
    assert item.error_code == "ACCESS_DENIED" and item.status == "reconciling"
    assert await queue.claim("no-auto-replay") is None
