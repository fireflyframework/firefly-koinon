# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.fixture
async def catalog(tmp_path: Path):
    from pyfly.core import PyFlyApplication

    from koinon.app import KoinonApplication
    from koinon.catalog.entities import Membership, Tenant
    from koinon.catalog.repositories import CatalogRepository, MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService

    config = tmp_path / "pyfly.yaml"
    config.write_text(
        "pyfly:\n  banner:\n    mode: off\n  data:\n    relational:\n"
        "      enabled: true\n      ddl-auto: create\n      url: sqlite+aiosqlite:///"
        + str(tmp_path / "catalog.db")
        + "\n"
    )
    app = PyFlyApplication(KoinonApplication, config_path=str(config))
    await app.startup()
    factory = app.context.get_bean(async_sessionmaker)
    async with factory() as session:
        tenants = app.context.get_bean(TenantRepository)
        members = app.context.get_bean(MembershipRepository)
        app.context.get_bean(CatalogRepository)
        for identifier in ("north", "south"):
            await tenants.save(Tenant(id=identifier, name=identifier.title()))
        for identifier, subject, tenant, role in [
            ("na", "alice", "north", "admin"),
            ("sb", "bob", "south", "admin"),
            ("nr", "reader", "north", "viewer"),
            ("nq", "analyst", "north", "analyst"),
        ]:
            await members.save(
                Membership(id=identifier, subject="issuer|" + subject, tenant_id=tenant, role=role)
            )
        await session.commit()
        yield app.context.get_bean(CatalogService), session, factory
    await app.shutdown()


async def test_persisted_membership_controls_authority(catalog):
    from koinon.catalog.errors import AccessDenied

    service, _, _ = catalog
    assert "query:execute" in await service.permissions("issuer|analyst", "north")
    assert "catalog:write" not in await service.permissions("issuer|analyst", "north")
    assert await service.permissions("issuer|alice", "south") == frozenset()
    with pytest.raises(AccessDenied):
        await service.authorize("issuer|reader", "north", "ingest:write")


async def test_every_hierarchy_ancestor_is_checked(catalog):
    from koinon.catalog.errors import AccessDenied, InvalidHierarchy

    service, _, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Research")
    project = await service.create(
        "issuer|alice", "north", kind="project", name="Quarterly", parent_id=workspace.id
    )
    assert project.workspace_id == workspace.id
    with pytest.raises(AccessDenied):
        await service.get("issuer|bob", "south", project.id)
    with pytest.raises(AccessDenied):
        await service.create("issuer|bob", "south", kind="project", name="Wrong", parent_id=workspace.id)
    with pytest.raises(InvalidHierarchy):
        await service.create("issuer|alice", "north", kind="dataset", name="Orphan", parent_id=workspace.id)


async def test_dual_source_assets_and_durable_provenance(catalog):
    service, session, factory = catalog
    parent = None
    for kind in ("workspace", "project", "collection", "source"):
        parent = (
            await service.create("issuer|alice", "north", kind=kind, name=kind.title(), parent_id=parent)
        ).id
    document = await service.create(
        "issuer|alice",
        "north",
        kind="document",
        name="Narrative",
        parent_id=parent,
        metadata={"sha256": "a" * 64, "media_type": "text/plain"},
    )
    dataset = await service.create(
        "issuer|alice",
        "north",
        kind="dataset",
        name="Numbers",
        parent_id=parent,
        metadata={"upstream_id": "original-dataset-id"},
    )
    assert document.project_id == dataset.project_id
    assert document.parent_id == dataset.parent_id == parent
    await session.commit()
    from koinon.catalog.entities import CatalogEntry, Membership, Tenant
    from koinon.catalog.repositories import CatalogRepository, MembershipRepository, TenantRepository
    from koinon.catalog.service import CatalogService

    async with factory() as fresh:
        reloaded = CatalogService(
            TenantRepository(Tenant, fresh),
            MembershipRepository(Membership, fresh),
            CatalogRepository(CatalogEntry, fresh),
        )
        assert (await reloaded.get("issuer|reader", "north", document.id)).metadata_json["sha256"] == "a" * 64
        assert {entry.kind for entry in await reloaded.list("issuer|reader", "north", parent_id=parent)} == {
            "document",
            "dataset",
        }


async def test_revocation_and_workspace_restriction(catalog):
    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    service, session, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Private")
    other = await service.create("issuer|alice", "north", kind="workspace", name="Other")
    await service.membership_repository.save(
        Membership(
            id="scoped", subject="issuer|scoped", tenant_id="north", workspace_id=workspace.id, role="editor"
        )
    )
    await session.commit()
    await service.authorize("issuer|scoped", "north", "catalog:write", workspace.id)
    for scope in (other.id, None):
        with pytest.raises(AccessDenied):
            await service.authorize("issuer|scoped", "north", "catalog:write", scope)
    await service.membership_repository.delete_by_id("scoped")
    await session.commit()
    with pytest.raises(AccessDenied):
        await service.authorize("issuer|scoped", "north", "catalog:write", workspace.id)


async def test_operator_can_configure_knowledge_but_cannot_grant_access(catalog):
    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    service, _, _ = catalog
    await service.membership_repository.save(
        Membership(id="north-operator", subject="issuer|operator", tenant_id="north", role="operator")
    )
    for permission in ("catalog:read", "ingest:write", "providers:write", "agents:write", "jobs:manage"):
        await service.authorize("issuer|operator", "north", permission)
    for permission in ("members:write", "identity:manage", "settings:write"):
        with pytest.raises(AccessDenied):
            await service.authorize("issuer|operator", "north", permission)


async def test_archived_folder_retains_content_hides_descendants_and_can_be_restored(catalog):
    service, _, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Research")
    project = await service.create(
        "issuer|alice", "north", kind="project", name="Team", parent_id=workspace.id
    )
    folder = await service.create(
        "issuer|alice", "north", kind="collection", name="Policies", parent_id=project.id
    )
    await service.archive("issuer|alice", "north", project.id)
    assert [row.id for row in await service.list("issuer|reader", "north")] == [workspace.id]
    assert (await service.get("issuer|alice", "north", folder.id)).name == "Policies"
    archived = await service.list("issuer|alice", "north", include_archived=True)
    assert {row.id for row in archived} == {workspace.id, project.id, folder.id}
    await service.restore("issuer|alice", "north", project.id)
    assert {row.id for row in await service.list("issuer|reader", "north")} == {
        workspace.id,
        project.id,
        folder.id,
    }


async def test_library_pagination_counts_projected_files_filters_and_stable_sort(catalog):
    service, _, _ = catalog
    parent = None
    for kind in ("workspace", "project", "collection"):
        parent = (await service.create("issuer|alice", "north", kind=kind, name=kind, parent_id=parent)).id
    source = await service.create("issuer|alice", "north", kind="source", name="Upload", parent_id=parent)
    for name in ("Policy B", "Policy A", "Policy C"):
        await service.create("issuer|alice", "north", kind="document", name=name, parent_id=source.id)
    pending = await service.create(
        "issuer|alice", "north", kind="source", name="Pending file", parent_id=parent
    )
    first = await service.page(
        "issuer|reader", "north", parent_id=parent, view="library", page=1, page_size=2
    )
    assert first["total"] == 4 and first["pages"] == 2
    assert [row.name for row in first["items"]] == ["Pending file", "Policy A"]
    second = await service.page(
        "issuer|reader", "north", parent_id=parent, view="library", page=2, page_size=2
    )
    assert [row.name for row in second["items"]] == ["Policy B", "Policy C"]
    filtered = await service.page(
        "issuer|reader", "north", parent_id=parent, view="library", q="Policy", page_size=2
    )
    assert filtered["total"] == 3
    await service.archive("issuer|alice", "north", pending.id)
    assert (await service.page("issuer|reader", "north", parent_id=parent, view="library"))["total"] == 3


async def test_processing_result_does_not_unarchive_a_file(catalog):
    service, _, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Research")
    await service.update("issuer|alice", "north", workspace.id, {"status": "pending"})
    await service.archive("issuer|alice", "north", workspace.id)
    await service.update("issuer|alice", "north", workspace.id, {"status": "error"})
    assert (await service.get("issuer|alice", "north", workspace.id)).status == "archived"
    assert (await service.restore("issuer|alice", "north", workspace.id)).status == "error"


async def test_project_filter_is_authorized_and_executed_before_pagination(catalog):
    from koinon.catalog.errors import AccessDenied, InvalidHierarchy

    service, _, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Workspace")
    other = await service.create("issuer|alice", "north", kind="workspace", name="Other")
    project = await service.create(
        "issuer|alice", "north", kind="project", name="Project", parent_id=workspace.id
    )
    collection = await service.create(
        "issuer|alice", "north", kind="collection", name="Specific result", parent_id=project.id
    )
    result = await service.page("issuer|reader", "north", project_id=project.id, q="Specific", page_size=1)
    assert result["total"] == 1 and result["items"][0].id == collection.id
    with pytest.raises(InvalidHierarchy):
        await service.page("issuer|alice", "north", project_id=project.id, workspace_id=other.id)
    with pytest.raises(AccessDenied):
        await service.page("issuer|bob", "south", project_id=project.id)
    with pytest.raises(InvalidHierarchy):
        await service.page("issuer|alice", "north", project_id=workspace.id)
