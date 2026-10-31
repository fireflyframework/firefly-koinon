# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from types import SimpleNamespace

import pytest
from organization_people_cases import A, B, C, H, S, W
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.organization_people.dtos import OrganizationDirectorySettingsInput as Settings
from koinon.organization_people.dtos import OrganizationPersonCreate as Create
from koinon.organization_people.dtos import OrganizationPersonPatch as Patch
from koinon.organization_people.dtos import OrganizationUnitInput as Unit
from koinon.organization_people.dtos import OrganizationUnitPatch as UnitPatch


async def test_default_is_admin_only_and_read_does_not_create_assignments(directory):
    d = directory
    with pytest.raises(AccessDenied):
        await d.service.page(B, "north", workspace_id=d.a)
    result = await d.service.page(A, "north")
    assert result.total == 5 and all(person.id is None and person.revision == 0 for person in result.items)
    assert (await d.service.self(B, "north", workspace_id=d.a)).source == "unassigned"
    assert await d.service.people.count() == 0


async def test_tenant_positions_are_distinct_and_never_change_roles(directory):
    d = directory
    before = await d.catalog.permissions(B, "north", d.a)
    north = await d.service.create(A, "north", Create(subject=B, job_title="Researcher"))
    south = await d.service.create(S, "south", Create(subject=B, job_title="Director"))
    assert north.job_title == "Researcher" and south.job_title == "Director" and north.id != south.id
    with pytest.raises(AccessDenied):
        await d.service.get(A, "north", south.id)
    with pytest.raises(AccessDenied):
        await d.service.update(A, "north", south.id, Patch(expected_revision=1, job_title="Changed"))
    assert (await d.service.self(B, "north", workspace_id=d.a)).job_title == "Researcher"
    assert await d.catalog.permissions(B, "north", d.a) == before
    assert "subject" not in north.model_dump() and "locale" not in north.model_dump()


async def test_workspace_admin_cannot_edit_tenant_metadata(directory):
    d = directory
    with pytest.raises(AccessDenied):
        await d.service.create(W, "north", Create(subject=C, job_title="Director"))
    with pytest.raises(AccessDenied):
        await d.service.create_unit(W, "north", Unit(name="Team"))


async def test_shared_workspace_filters_people_managers_units_and_counts(directory):
    d = directory
    visible = await d.service.create_unit(A, "north", Unit(name="Visible"))
    hidden = await d.service.create_unit(A, "north", Unit(name="Private"))
    boss = await d.service.create(
        A, "north", Create(subject=H, job_title="Hidden manager", unit_id=hidden.id)
    )
    member = await d.service.create(
        A, "north", Create(subject=B, job_title="Researcher", unit_id=visible.id, manager_id=boss.id)
    )
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    result = await d.service.page(B, "north", workspace_id=d.a)
    assert result.total == 4
    assert {row.display_name for row in result.items} == {
        "Administrator",
        "Member",
        "Colleague",
        "Workspace admin",
    }
    current = next(row for row in result.items if row.id == member.id)
    assert current.manager is None and current.manager_unavailable
    assert current.unit.name == "Visible"
    units = await d.service.units(B, "north", workspace_id=d.a)
    assert [row.name for row in units.items] == ["Visible"]
    assert (await d.service.page(B, "north", workspace_id=d.a, q="Private")).total == 0
    with pytest.raises(AccessDenied):
        await d.service.get(B, "north", boss.id, workspace_id=d.a)
    with pytest.raises(AccessDenied):
        await d.service.avatar(B, "north", boss.id, workspace_id=d.a)
    with pytest.raises(AccessDenied):
        await d.service.reports(B, "north", boss.id, workspace_id=d.a)
    with pytest.raises(AccessDenied):
        await d.service.page(B, "north")


async def test_unit_and_manager_cycles_and_cross_tenant_links_are_rejected(directory):
    d = directory
    root = await d.service.create_unit(A, "north", Unit(name="Department"))
    child = await d.service.create_unit(A, "north", Unit(name="Team", parent_id=root.id, kind="team"))
    other = await d.service.create_unit(S, "south", Unit(name="Other"))
    with pytest.raises(ConflictException):
        await d.service.update_unit(A, "north", root.id, UnitPatch(expected_revision=1, parent_id=child.id))
    with pytest.raises(AccessDenied):
        await d.service.create(A, "north", Create(subject=B, unit_id=other.id))
    one = await d.service.create(A, "north", Create(subject=B, unit_id=child.id))
    two = await d.service.create(A, "north", Create(subject=C, manager_id=one.id))
    with pytest.raises(ConflictException):
        await d.service.update(A, "north", one.id, Patch(expected_revision=1, manager_id=two.id))
    with pytest.raises(ConflictException):
        await d.service.delete_unit(A, "north", root.id, 1)
    with pytest.raises(ConflictException):
        await d.service.delete_unit(A, "north", child.id, 1)
    assert (await d.service.get(A, "north", one.id)).department.name == "Department"


async def test_optimistic_revision_and_null_clear_preserve_other_fields(directory):
    d = directory
    row = await d.service.create(A, "north", Create(subject=B, job_title="Analyst"))
    updated = await d.service.update(A, "north", row.id, Patch(expected_revision=1, job_title=None))
    assert updated.job_title is None and updated.revision == 2
    with pytest.raises(ConflictException):
        await d.service.update(A, "north", row.id, Patch(expected_revision=1, job_title="Stale"))
    with pytest.raises(ConflictException):
        await d.service.create(A, "north", Create(subject=B))


async def test_concurrent_unit_cycle_is_serialized_by_native_tenant_lock(directory):
    d = directory
    one = await d.service.create_unit(A, "north", Unit(name="One"))
    two = await d.service.create_unit(A, "north", Unit(name="Two"))
    outcomes = await asyncio.gather(
        d.service.update_unit(A, "north", one.id, UnitPatch(expected_revision=1, parent_id=two.id)),
        d.service.update_unit(A, "north", two.id, UnitPatch(expected_revision=1, parent_id=one.id)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ConflictException) for result in outcomes) == 1


async def test_personal_token_workspace_and_asset_limits_fail_closed(directory):
    d = directory
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    original = d.catalog.restriction
    grant = SimpleNamespace(
        tenant_id="north", workspace_ids=[d.a], asset_ids=None, scopes=["catalog:read", "profile:read"]
    )

    async def token(_):
        return grant

    d.catalog.restriction = SimpleNamespace(grant=token)
    try:
        assert (await d.service.page(B, "north", workspace_id=d.a)).total == 4
        with pytest.raises(AccessDenied):
            await d.service.page(B, "north", workspace_id=d.b)
        grant.asset_ids = ["private-file"]
        with pytest.raises(AccessDenied):
            await d.service.page(B, "north", workspace_id=d.a)
        with pytest.raises(AccessDenied):
            await d.service.self(B, "north", workspace_id=d.a)
    finally:
        d.catalog.restriction = original


async def test_target_departure_during_await_prevents_response(directory, monkeypatch):
    d = directory
    row = await d.service.create(A, "north", Create(subject=B))
    original = d.service.people.summaries

    async def depart(*args, **kwargs):
        result = await original(*args, **kwargs)
        from sqlalchemy import select

        monkeypatch.setattr(
            d.catalog,
            "effective_membership_rows",
            lambda: (
                select(Membership)
                .where(Membership.active.is_(True), Membership.subject != B)
                .subquery("departed_members")
            ),
        )
        return result

    monkeypatch.setattr(d.service.people, "summaries", depart)
    with pytest.raises(AccessDenied):
        await d.service.get(A, "north", row.id)


async def test_reparenting_a_branch_cannot_push_descendants_beyond_depth_bound(directory):
    d = directory
    from koinon.organization_people.entities import OrganizationUnitRecord

    parent = None
    for index in range(31):
        row = OrganizationUnitRecord(
            id=f"deep-{index}",
            tenant_id="north",
            name=f"Unit {index}",
            kind="team",
            parent_id=parent,
            revision=1,
            updated_by=A,
        )
        await d.service.unit_repository.save(row)
        parent = row.id
    branch = await d.service.create_unit(A, "north", Unit(name="Branch"))
    await d.service.create_unit(A, "north", Unit(name="Leaf", parent_id=branch.id))
    with pytest.raises(ConflictException):
        await d.service.update_unit(A, "north", branch.id, UnitPatch(expected_revision=1, parent_id=parent))


async def test_shared_unit_projection_is_rechecked_after_await(directory, monkeypatch):
    d = directory
    unit = await d.service.create_unit(A, "north", Unit(name="Only visible through member"))
    await d.service.create(A, "north", Create(subject=B, unit_id=unit.id))
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    original = d.service.unit_repository.page

    async def depart(*args, **kwargs):
        result = await original(*args, **kwargs)
        from sqlalchemy import select

        monkeypatch.setattr(
            d.catalog,
            "effective_membership_rows",
            lambda: (
                select(Membership)
                .where(Membership.active.is_(True), Membership.subject != B)
                .subquery("departed_unit_members")
            ),
        )
        return result

    monkeypatch.setattr(d.service.unit_repository, "page", depart)
    with pytest.raises(AccessDenied):
        await d.service.units(C, "north", workspace_id=d.a)


async def test_hidden_manager_filter_is_not_a_relationship_oracle(directory):
    d = directory
    manager = await d.service.create(A, "north", Create(subject=H))
    await d.service.create(A, "north", Create(subject=B, manager_id=manager.id))
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    with pytest.raises(AccessDenied):
        await d.service.page(C, "north", workspace_id=d.a, manager_id=manager.id)


async def test_unassigned_visible_person_avatar_needs_no_assignment_write(directory):
    from io import BytesIO

    from PIL import Image

    d = directory
    content = BytesIO()
    Image.new("RGB", (8, 8)).save(content, format="PNG")
    await d.profiles.set_avatar(B, content.getvalue())
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    page = await d.service.page(C, "north", workspace_id=d.a)
    person = next(row for row in page.items if row.display_name == "Member")
    assert person.id is None and person.avatar_url and person.profile_id in person.avatar_url
    assert await d.service.avatar(C, "north", person.profile_id, workspace_id=d.a) == await d.profiles.avatar(
        B
    )
    assert await d.service.people.count() == 0


async def test_concurrent_reporting_cycle_has_only_one_success(directory):
    d = directory
    one = await d.service.create(A, "north", Create(subject=B))
    two = await d.service.create(A, "north", Create(subject=C))
    outcomes = await asyncio.gather(
        d.service.update(A, "north", one.id, Patch(expected_revision=1, manager_id=two.id)),
        d.service.update(A, "north", two.id, Patch(expected_revision=1, manager_id=one.id)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, ConflictException) for result in outcomes) == 1


async def test_profile_identifier_create_and_stable_filtered_pagination(directory):
    from koinon.profiles.service import profile_id

    d = directory
    unit = await d.service.create_unit(A, "north", Unit(name="Engineering"))
    row = await d.service.create(
        A, "north", Create(profile_id=profile_id(B), job_title="Engineer", unit_id=unit.id)
    )
    assert row.updated_at is not None and unit.updated_at is not None
    found = await d.service.page(A, "north", job_title="Engineer", unit_id=unit.id, page_size=1)
    assert found.total == 1 and found.pages == 1 and found.items[0].id == row.id
    page = await d.service.page(A, "north", page=2, page_size=2)
    assert len(page.items) == 2 and page.total == 5 and page.pages == 3
    with pytest.raises(InvalidRequestException):
        await d.service.page(A, "north", page_size=51)
    with pytest.raises(AccessDenied):
        await d.service.page(A, "north", unit_id="other-tenant-unit")


async def test_native_composite_tenant_foreign_key_rejects_bypassed_cross_tenant_unit(directory):
    from pyfly.kernel import DataIntegrityException

    from koinon.organization_people.entities import OrganizationPersonRecord

    d = directory
    unit = await d.service.create_unit(S, "south", Unit(name="Other tenant"))
    with pytest.raises(DataIntegrityException):
        await d.service.people.save(
            OrganizationPersonRecord(id="forged", tenant_id="north", subject=B, unit_id=unit.id, updated_by=A)
        )


async def test_visibility_revocation_during_await_uses_current_settings(directory, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.organization_people.entities import OrganizationDirectorySettingRecord

    d = directory
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    original = d.service.people.summaries

    async def revoke(*args, **kwargs):
        result = await original(*args, **kwargs)
        engine = d.context.get_bean(DataSourceRegistry).primary.engine
        async with engine.begin() as connection:
            await connection.execute(
                update(OrganizationDirectorySettingRecord)
                .where(OrganizationDirectorySettingRecord.tenant_id == "north")
                .values(visibility="administrators", revision=2)
            )
        return result

    monkeypatch.setattr(d.service.people, "summaries", revoke)
    with pytest.raises(AccessDenied):
        await d.service.page(B, "north", workspace_id=d.a)


async def test_self_manager_is_hidden_if_visibility_changes_at_last_membership_await(directory, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.organization_people.entities import OrganizationDirectorySettingRecord

    d = directory
    manager = await d.service.create(A, "north", Create(subject=C))
    await d.service.create(A, "north", Create(subject=B, manager_id=manager.id))
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    original = d.service._member
    revoked = False

    async def revoke(tenant_id, subject, workspace_id=None):
        nonlocal revoked
        await original(tenant_id, subject, workspace_id)
        if subject == B and not revoked:
            revoked = True
            async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
                await connection.execute(
                    update(OrganizationDirectorySettingRecord)
                    .where(OrganizationDirectorySettingRecord.tenant_id == "north")
                    .values(visibility="administrators", revision=2)
                )

    monkeypatch.setattr(d.service, "_member", revoke)
    with pytest.raises(AccessDenied):
        await d.service.self(B, "north", workspace_id=d.a)


async def test_nonpage_departure_does_not_leak_stale_total(directory, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    d = directory
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    original = d.service.people.summaries

    async def revoke(*args, **kwargs):
        result = await original(*args, **kwargs)
        async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
            await connection.execute(
                update(Membership)
                .where(Membership.tenant_id == "north", Membership.subject == C)
                .values(active=False)
            )
        return result

    monkeypatch.setattr(d.service.people, "summaries", revoke)
    with pytest.raises(AccessDenied):
        await d.service.page(B, "north", workspace_id=d.a, page_size=1)


async def test_child_flag_does_not_reveal_departed_child_unit_member(directory, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    d = directory
    root = await d.service.create_unit(A, "north", Unit(name="Visible root"))
    child = await d.service.create_unit(A, "north", Unit(name="Private after departure", parent_id=root.id))
    await d.service.create(A, "north", Create(subject=B, unit_id=root.id))
    await d.service.create(A, "north", Create(subject=C, unit_id=child.id))
    await d.service.update_settings(A, "north", Settings(expected_revision=0, visibility="shared_workspaces"))
    original = d.service.unit_repository.page
    revoked = False

    async def revoke(*args, **kwargs):
        nonlocal revoked
        result = await original(*args, **kwargs)
        if not revoked:
            revoked = True
            async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
                await connection.execute(
                    update(Membership)
                    .where(Membership.tenant_id == "north", Membership.subject == C)
                    .values(active=False)
                )
        return result

    monkeypatch.setattr(d.service.unit_repository, "page", revoke)
    with pytest.raises(AccessDenied):
        await d.service.units(B, "north", workspace_id=d.a)


async def test_directory_settings_rechecks_membership_after_repository_await(directory, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    d = directory
    original = d.service.setting_repository.find_by_id

    async def revoke(*args, **kwargs):
        result = await original(*args, **kwargs)
        async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
            await connection.execute(
                update(Membership)
                .where(Membership.tenant_id == "north", Membership.subject == B)
                .values(active=False)
            )
        return result

    monkeypatch.setattr(d.service.setting_repository, "find_by_id", revoke)
    with pytest.raises(AccessDenied):
        await d.service.settings(B, "north")
