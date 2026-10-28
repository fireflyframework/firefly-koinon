# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""A derived item's ACL cannot expand its source roots."""

import pytest
from test_curated_intents import curated as curated


async def test_library_total_respects_all_source_root_workspaces(curated):
    from koinon.catalog.entities import CatalogEntry, Membership
    from koinon.catalog.repositories import MembershipRepository
    from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot
    from koinon.knowledge.curated.repositories import (
        CuratedCatalogStateRepository,
        CuratedSourceRootRepository,
    )

    _, catalog, destination, context = curated
    workspace = await catalog.create("issuer|owner", "north", kind="workspace", name="Restricted")
    parent = workspace
    for kind in ("project", "collection", "source", "document"):
        parent = await catalog.create("issuer|owner", "north", kind=kind, name=kind, parent_id=parent.id)
    item = CatalogEntry(
        id="published",
        tenant_id="north",
        workspace_id=destination.workspace_id,
        project_id=destination.project_id,
        parent_id=destination.id,
        kind="knowledge_item",
        name="Curated fact",
        description="",
        status="ready",
        metadata_json={},
        created_by="issuer|owner",
        updated_by="issuer|owner",
    )
    await catalog.catalog_repository.save(item)
    state = CuratedCatalogState(
        item_id=item.id,
        tenant_id="north",
        workspace_id=item.workspace_id,
        native_item_id="native",
        native_workspace_id="native-space",
        head_version=1,
        head_version_id="version",
        serving_version=1,
        serving_version_id="version",
        serving_operation_id="operation",
        head_operation_id="operation",
        root_count=1,
    )
    await context.get_bean(CuratedCatalogStateRepository).save(state)
    await context.get_bean(CuratedSourceRootRepository).save(
        CuratedSourceRoot(
            id="root",
            tenant_id="north",
            item_id=item.id,
            native_version_id="version",
            source_asset_id=parent.id,
        )
    )
    memberships = context.get_bean(MembershipRepository)
    membership = await memberships.find_by_id("reader")
    membership.workspace_id = destination.workspace_id
    await memberships.save(membership)
    from koinon.catalog.errors import AccessDenied

    with pytest.raises(AccessDenied):
        await catalog.get("issuer|reader", "north", item.id)
    page = await catalog.page("issuer|reader", "north", parent_id=destination.id, view="library")
    assert page["total"] == 0 and page["items"] == []
    await memberships.save(
        Membership(
            id="reader-root",
            tenant_id="north",
            subject="issuer|reader",
            role="viewer",
            workspace_id=workspace.id,
        )
    )
    page = await catalog.page("issuer|reader", "north", parent_id=destination.id, view="library")
    assert page["total"] == 1 and [row.id for row in page["items"]] == [item.id]
    assert (await catalog.get("issuer|reader", "north", item.id)).id == item.id


async def test_generic_catalog_creation_cannot_bypass_knowledge_review(curated):
    from koinon.catalog.errors import InvalidHierarchy

    _, catalog, destination, _ = curated
    with pytest.raises(InvalidHierarchy) as failure:
        await catalog.create(
            "issuer|owner", "north", kind="knowledge_item", name="Bypass", parent_id=destination.id
        )
    assert failure.value.code == "KNOWLEDGE_REVIEW_REQUIRED"
