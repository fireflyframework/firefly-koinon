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


async def test_library_summaries_use_complete_visible_projection_and_unknown_metadata(catalog):
    service, _, _ = catalog
    parent = None
    entries = {}
    for kind in ("workspace", "project", "collection", "source"):
        item = await service.create("issuer|alice", "north", kind=kind, name=kind, parent_id=parent)
        entries[kind] = item
        parent = item.id
    document = await service.create(
        "issuer|alice",
        "north",
        kind="document",
        name="Policy.PDF",
        parent_id=parent,
        metadata={"bytes": 2048, "page_count": 3, "language": "EN", "tags": [" Reviewed ", "reviewed"]},
    )
    dataset = await service.create("issuer|alice", "north", kind="dataset", name="Unknown", parent_id=parent)
    await service.create("issuer|alice", "north", kind="table", name="Facts", parent_id=dataset.id)
    result = await service.page(
        "issuer|reader", "north", parent_id=entries["project"].id, view="library", page_size=1
    )
    assert result["summaries"][entries["collection"].id]["child_count"] == 2
    assert result["summaries"][entries["collection"].id]["document_count"] == 1
    files = await service.page("issuer|reader", "north", parent_id=entries["collection"].id, view="library")
    summary = files["summaries"][document.id]
    assert summary["format"] == "pdf"
    assert summary["tags"] == ["pdf", "en", "Reviewed"]
    assert summary["size_bytes"] == 2048 and summary["page_count"] == 3
    assert files["summaries"][dataset.id]["row_count"] is None
    assert files["summaries"][dataset.id]["column_count"] is None
    assert files["summaries"][dataset.id]["table_count"] == 1
    await service.archive("issuer|alice", "north", document.id)
    result = await service.page("issuer|reader", "north", parent_id=entries["project"].id, view="library")
    assert result["summaries"][entries["collection"].id]["child_count"] == 1


async def test_library_format_tag_and_kind_sort_apply_before_pagination(catalog):
    service, _, _ = catalog
    parent = None
    for kind in ("workspace", "project", "collection", "source"):
        parent = (await service.create("issuer|alice", "north", kind=kind, name=kind, parent_id=parent)).id
    for name, kind, tags in [
        ("A.csv", "dataset", []),
        ("Z.pdf", "document", ["Reviewed"]),
        ("B.pdf", "document", ["reviewed"]),
    ]:
        await service.create(
            "issuer|alice", "north", kind=kind, name=name, parent_id=parent, metadata={"tags": tags}
        )
    result = await service.page(
        "issuer|reader", "north", parent_id=parent, format="pdf", tag="REVIEWED", page_size=1, page=2
    )
    assert result["total"] == 2 and result["items"][0].name == "Z.pdf"
    result = await service.page(
        "issuer|reader", "north", parent_id=parent, sort="kind", order="desc", page_size=1
    )
    assert result["items"][0].kind == "document"
    assert (await service.page("issuer|reader", "north", parent_id=parent, tag="csv"))["total"] == 1
    from koinon.catalog.errors import InvalidHierarchy

    for filters in (
        {"tag": "x" * 65},
        {"format": "unknown"},
        {"kind": "not-a-kind"},
        {"status": "not-a-status"},
        {"page": 1000001},
    ):
        with pytest.raises(InvalidHierarchy):
            await service.page("issuer|reader", "north", **filters)


async def test_summary_queries_are_batched_and_workspace_revocation_is_current(catalog):
    from sqlalchemy import event

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    service, session, _ = catalog
    workspaces = []
    for name in ("Visible", "Other"):
        workspace = await service.create("issuer|alice", "north", kind="workspace", name=name)
        workspaces.append(workspace)
        for number in range(3):
            await service.create(
                "issuer|alice", "north", kind="project", name=f"Project {number}", parent_id=workspace.id
            )
    await service.membership_repository.save(
        Membership(
            id="summary-member",
            subject="issuer|summary",
            tenant_id="north",
            workspace_id=workspaces[0].id,
            role="viewer",
        )
    )
    statements = []

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "lattice_catalog" in statement and (
            statement.startswith("SELECT") or statement.startswith("WITH")
        ):
            statements.append(statement)

    engine = session.bind.sync_engine
    event.listen(engine, "before_cursor_execute", observe)
    try:
        one = await service.page("issuer|summary", "north", page_size=1)
        small = len(statements)
        statements.clear()
        all_rows = await service.page("issuer|summary", "north", page_size=100)
        assert small == len(statements) == 4
        assert all(row.workspace_id == workspaces[0].id for row in all_rows["items"])
        assert one["total"] == all_rows["total"] == 4
        assert all_rows["summaries"][workspaces[0].id]["child_count"] == 3
    finally:
        event.remove(engine, "before_cursor_execute", observe)
    await service.membership_repository.delete_by_id("summary-member")
    with pytest.raises(AccessDenied):
        await service.page("issuer|summary", "north")


async def test_summary_ignores_malformed_numbers_and_non_string_tags(catalog):
    service, _, _ = catalog
    item = await service.create(
        "issuer|alice",
        "north",
        kind="workspace",
        name="Metrics",
        metadata={
            "row_count": True,
            "column_count": -1,
            "page_count": "10",
            "bytes": 9007199254740992,
            "language": 123,
            "tags": [123, None, {"secret": "nested"}, " Valid "],
            "_not_an_internal_marker": "public",
        },
    )
    page = await service.page("issuer|reader", "north", tag="valid")
    summary = page["summaries"][item.id]
    assert summary["tags"] == ["Valid"]
    assert all(summary[key] is None for key in ("row_count", "column_count", "page_count", "size_bytes"))
    assert (await service.page("issuer|reader", "north", tag="123"))["total"] == 0


async def test_folder_filename_suffix_does_not_invent_a_file_format(catalog):
    service, _, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Budget.xlsx")
    page = await service.page("issuer|reader", "north", kind="workspace")
    assert page["summaries"][workspace.id]["format"] is None
    assert page["summaries"][workspace.id]["tags"] == []
    assert (await service.page("issuer|reader", "north", format="xlsx"))["total"] == 0
    assert (await service.page("issuer|reader", "north", tag="xlsx"))["total"] == 0
    await service.update("issuer|alice", "north", workspace.id, {"metadata": {"format": "xlsx"}})
    assert (await service.page("issuer|reader", "north", format="xlsx"))["total"] == 1


async def test_dataset_summary_does_not_treat_original_source_bytes_as_aggregate(catalog):
    service, _, _ = catalog
    parent = None
    for kind in ("workspace", "project", "collection", "source"):
        parent = (
            await service.create(
                "issuer|alice",
                "north",
                kind=kind,
                name=kind,
                parent_id=parent,
                metadata={"bytes": 100} if kind == "source" else {},
            )
        ).id
    dataset = await service.create("issuer|alice", "north", kind="dataset", name="Data", parent_id=parent)
    document = await service.create("issuer|alice", "north", kind="document", name="File", parent_id=parent)
    await service.create(
        "issuer|alice",
        "north",
        kind="index_version",
        name="more.csv",
        parent_id=dataset.id,
        metadata={"bytes": 50},
    )
    page = await service.page("issuer|reader", "north", parent_id=parent)
    assert page["summaries"][dataset.id]["size_bytes"] is None
    assert page["summaries"][document.id]["size_bytes"] == 100
    await service.update("issuer|alice", "north", dataset.id, {"metadata": {"size_bytes": 150}})
    page = await service.page("issuer|reader", "north", parent_id=parent)
    assert page["summaries"][dataset.id]["size_bytes"] == 150


async def test_custom_tag_display_preserves_case_and_filter_matching_is_normalized(catalog):
    service, _, _ = catalog
    workspace = await service.create(
        "issuer|alice",
        "north",
        kind="workspace",
        name="Labels",
        metadata={"tags": [" Finance ", "PII", "finance", "pii", "API"]},
    )
    page = await service.page("issuer|reader", "north", tag="finance")
    assert page["summaries"][workspace.id]["tags"] == ["Finance", "PII", "API"]
    assert (await service.page("issuer|reader", "north", tag="PII"))["total"] == 1


async def test_system_workspace_cannot_be_deleted_archived_or_stripped_of_protection(catalog):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import InvalidHierarchy
    from koinon.catalog.mappers import entry_dto

    service, session, _ = catalog
    root = await service._write_create(
        "system:installation",
        "north",
        kind="workspace",
        name="Organization",
        create_id="system-space",
        installation_run_id="installation-run",
        system_key="organization",
    )
    await session.commit()
    assert root.workspace_id == root.id
    assert root.system_key == "organization"
    assert root.installation_run_id == "installation-run"
    assert entry_dto(root)["system_managed"] is True
    for operation in (service.delete, service.archive):
        with pytest.raises(ConflictException, match="System knowledge spaces"):
            await operation("issuer|alice", "north", root.id)
    for field in ("system_key", "installation_run_id"):
        with pytest.raises(InvalidHierarchy):
            await service.update("issuer|alice", "north", root.id, {field: None})
    root = await service.update("issuer|alice", "north", root.id, {"metadata": {"tags": ["team"]}})
    assert root.system_key == "organization"
    assert root.installation_run_id == "installation-run"
    assert root.status == "ready"


async def test_ordinary_user_workspaces_remain_deletable_and_cannot_claim_system_fields(catalog):
    from pydantic import ValidationError

    from koinon.catalog.dtos import CatalogCreate, CatalogPatch
    from koinon.catalog.mappers import entry_dto

    service, _, _ = catalog
    root = await service.create("issuer|alice", "north", kind="workspace", name="User space")
    assert entry_dto(root)["system_managed"] is False
    await service.delete("issuer|alice", "north", root.id)
    for model in (CatalogCreate, CatalogPatch):
        fields = {"kind": "workspace", "name": "Forged"} if model is CatalogCreate else {}
        with pytest.raises(ValidationError):
            model.model_validate({**fields, "system_key": "organization"})


async def test_nested_folder_move_preserves_native_scope_and_records_old_and_new_location(catalog):
    from koinon.catalog.hierarchy_service import CatalogHierarchyService

    service, session, _ = catalog
    workspace = await service.create("issuer|alice", "north", kind="workspace", name="Space")
    project = await service.create(
        "issuer|alice", "north", kind="project", name="Team", parent_id=workspace.id
    )
    origin = await service.create(
        "issuer|alice", "north", kind="collection", name="Origin", parent_id=project.id
    )
    destination = await service.create(
        "issuer|alice", "north", kind="collection", name="Destination", parent_id=project.id
    )
    child = await service.create("issuer|alice", "north", kind="corpus", name="Nested", parent_id=origin.id)
    original_time = child.updated_at
    moved = await CatalogHierarchyService(service).move(
        "issuer|alice",
        "north",
        child.id,
        parent_id=destination.id,
        expected_parent_id=origin.id,
        expected_updated_at=original_time,
    )
    assert (moved.parent_id, moved.workspace_id, moved.project_id) == (
        destination.id,
        workspace.id,
        project.id,
    )
    events = await service.audit_repository.find_all(tenant_id="north", action="catalog.moved")
    assert len(events) == 1
    assert events[0].details == {"from_parent_id": origin.id, "to_parent_id": destination.id}
    await session.commit()
    page = await service.page("issuer|reader", "north", parent_id=destination.id, view="library")
    assert [row.id for row in page["items"]] == [child.id]


async def test_folder_moves_reject_cycles_stale_state_cross_space_and_read_only_users(catalog):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import AccessDenied, InvalidHierarchy
    from koinon.catalog.hierarchy_service import CatalogHierarchyService

    service, _, _ = catalog
    root = await service.create("issuer|alice", "north", kind="workspace", name="Space")
    project = await service.create("issuer|alice", "north", kind="project", name="Team", parent_id=root.id)
    origin = await service.create(
        "issuer|alice", "north", kind="collection", name="Origin", parent_id=project.id
    )
    child = await service.create(
        "issuer|alice", "north", kind="collection", name="Child", parent_id=origin.id
    )
    hierarchy = CatalogHierarchyService(service)
    with pytest.raises(InvalidHierarchy, match="cycle"):
        await hierarchy.move(
            "issuer|alice",
            "north",
            origin.id,
            parent_id=child.id,
            expected_parent_id=project.id,
            expected_updated_at=origin.updated_at,
        )
    with pytest.raises(ConflictException):
        await hierarchy.move(
            "issuer|alice",
            "north",
            child.id,
            parent_id=project.id,
            expected_parent_id="stale",
            expected_updated_at=child.updated_at,
        )
    with pytest.raises(AccessDenied):
        await hierarchy.move(
            "issuer|reader",
            "north",
            child.id,
            parent_id=project.id,
            expected_parent_id=origin.id,
            expected_updated_at=child.updated_at,
        )
    other = await service.create("issuer|alice", "north", kind="workspace", name="Other")
    other_project = await service.create(
        "issuer|alice", "north", kind="project", name="Other team", parent_id=other.id
    )
    with pytest.raises(InvalidHierarchy, match="transfer"):
        await hierarchy.move(
            "issuer|alice",
            "north",
            child.id,
            parent_id=other_project.id,
            expected_parent_id=origin.id,
            expected_updated_at=child.updated_at,
        )
    assert child.parent_id == origin.id


async def test_nested_folder_creation_and_moves_enforce_depth_and_processing_limits(catalog):
    from pyfly.kernel import ConflictException

    from koinon.catalog.errors import InvalidHierarchy
    from koinon.catalog.hierarchy_service import CatalogHierarchyService

    service, _, _ = catalog
    root = await service.create("issuer|alice", "north", kind="workspace", name="Space")
    project = await service.create("issuer|alice", "north", kind="project", name="Team", parent_id=root.id)
    parent = project
    for depth in range(10):
        parent = await service.create(
            "issuer|alice", "north", kind="collection", name=f"Level {depth}", parent_id=parent.id
        )
    with pytest.raises(InvalidHierarchy, match="shallower"):
        await service.create("issuer|alice", "north", kind="collection", name="Too deep", parent_id=parent.id)
    source = await service.create(
        "issuer|alice", "north", kind="source", name="Original", parent_id=parent.id
    )
    asset = await service.create(
        "issuer|alice", "north", kind="document", name="Document", parent_id=source.id
    )
    await service.create("issuer|alice", "north", kind="chunk", name="Passage", parent_id=asset.id)
    await service.update("issuer|alice", "north", source.id, {"status": "pending"})
    with pytest.raises(ConflictException, match="processing"):
        await CatalogHierarchyService(service).move(
            "issuer|alice",
            "north",
            parent.id,
            parent_id=project.id,
            expected_parent_id=parent.parent_id,
            expected_updated_at=parent.updated_at,
        )


async def test_archived_parent_does_not_accept_new_nested_content(catalog):
    from koinon.catalog.errors import InvalidHierarchy

    service, _, _ = catalog
    root = await service.create("issuer|alice", "north", kind="workspace", name="Space")
    project = await service.create("issuer|alice", "north", kind="project", name="Team", parent_id=root.id)
    await service.archive("issuer|alice", "north", project.id)
    with pytest.raises(InvalidHierarchy, match="active"):
        await service.create("issuer|alice", "north", kind="collection", name="Hidden", parent_id=project.id)


async def test_installed_child_folders_are_protected_without_creating_new_knowledge_boundaries(catalog):
    from pyfly.kernel import ConflictException

    from koinon.catalog.hierarchy_service import CatalogHierarchyService

    service, _, _ = catalog
    parent = None
    for kind in ("workspace", "project", "collection"):
        entry = await service._write_create(
            "system:installation",
            "north",
            kind=kind,
            name=kind,
            parent_id=parent,
            installation_run_id="run",
            system_key=f"default-{kind}",
        )
        parent = entry.id
    for operation in (service.delete, service.archive):
        with pytest.raises(ConflictException):
            await operation("issuer|alice", "north", entry.id)
    with pytest.raises(ConflictException):
        await CatalogHierarchyService(service).move(
            "issuer|alice",
            "north",
            entry.id,
            parent_id=entry.project_id,
            expected_parent_id=entry.parent_id,
            expected_updated_at=entry.updated_at,
        )
    child = await service.create(
        "issuer|alice", "north", kind="collection", name="User folder", parent_id=entry.id
    )
    assert (child.workspace_id, child.project_id) == (entry.workspace_id, entry.project_id)
    await service.delete("issuer|alice", "north", child.id)
