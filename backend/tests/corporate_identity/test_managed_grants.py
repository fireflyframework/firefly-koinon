# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from test_provider_service import identities as identities
from test_provider_service import local_input

from koinon.catalog.entities import Membership
from koinon.catalog.repositories import MembershipRepository
from koinon.catalog.service import CatalogService
from koinon.corporate_identity.entities import CorporateMapping
from koinon.corporate_identity.policy import CorporateIdentity, DirectorySnapshot
from koinon.corporate_identity.repositories import CorporateMappingRepository, CorporateProviderRepository


async def test_managed_groups_are_separate_expiring_and_revocable_without_manual_mutation(identities):
    service, context = identities
    catalog = context.get_bean(CatalogService)
    workspace = await catalog.create("issuer|admin", "north", kind="workspace", name="Managed scope")
    await context.get_bean(MembershipRepository).save(
        Membership(
            id="manual-viewer",
            subject="https://identity.example.test/realms/koinon|member",
            tenant_id="north",
            role="viewer",
        )
    )
    provider = await service.create("issuer|admin", "north", local_input())
    row = await context.get_bean(CorporateProviderRepository).find_by_id(provider.id)
    row.status = "active"
    await context.get_bean(CorporateProviderRepository).save(row)
    await context.get_bean(CorporateMappingRepository).save(
        CorporateMapping(
            id="rule",
            tenant_id="north",
            provider_id=provider.id,
            group_id="group-one",
            group_name="Researchers",
            role="editor",
            workspace_id=workspace.id,
            enabled=True,
            revision=1,
        )
    )
    identity = CorporateIdentity("https://identity.example.test/realms/koinon|member", "member", False)
    now = datetime.now(UTC)
    snapshot = DirectorySnapshot("member", frozenset({"group-one"}), True, now, now + timedelta(seconds=60))
    await service.reconcile(provider.id, identity, snapshot, expected_policy_revision=1)
    assert "catalog:write" in await catalog.permissions(identity.subject, "north", workspace.id)
    assert "catalog:write" not in await catalog.permissions(identity.subject, "north")
    assert (
        len(
            await context.get_bean(MembershipRepository).find_all(subject=identity.subject, tenant_id="north")
        )
        == 1
    )
    empty = DirectorySnapshot("member", frozenset(), True, now, now + timedelta(seconds=60))
    await service.reconcile(provider.id, identity, empty, expected_policy_revision=1)
    assert "catalog:write" not in await catalog.permissions(identity.subject, "north", workspace.id)
    assert "catalog:read" in await catalog.permissions(identity.subject, "north")
    await service.reconcile(provider.id, identity, snapshot, expected_policy_revision=1)
    await service.disable("issuer|admin", "north", provider.id, expected_revision=1)
    assert "catalog:write" not in await catalog.permissions(identity.subject, "north", workspace.id)
    assert (await context.get_bean(MembershipRepository).find_all(id="manual-viewer"))[0].active is True


async def test_people_projection_counts_filters_and_pages_both_origins_with_read_only_provenance(identities):
    from koinon.catalog.mappers import member_dto
    from koinon.profiles.service import ProfileService

    service, context = identities
    catalog = context.get_bean(CatalogService)
    subject = "https://identity.example.test/realms/koinon|researcher"
    await context.get_bean(MembershipRepository).save(
        Membership(id="manual-researcher", subject=subject, tenant_id="north", role="viewer")
    )
    await context.get_bean(ProfileService).update(subject, {"display_name": "Research person"})
    provider = await service.create("issuer|admin", "north", local_input())
    row = await context.get_bean(CorporateProviderRepository).find_by_id(provider.id)
    row.status = "active"
    await context.get_bean(CorporateProviderRepository).save(row)
    await context.get_bean(CorporateMappingRepository).save(
        CorporateMapping(
            id="projection-rule",
            tenant_id="north",
            provider_id=provider.id,
            group_id="research",
            group_name="Researchers",
            role="editor",
            workspace_id=None,
            enabled=True,
            revision=1,
        )
    )
    now = datetime.now(UTC)
    await service.reconcile(
        provider.id,
        CorporateIdentity(subject, "researcher", False),
        DirectorySnapshot("researcher", frozenset({"research"}), True, now, now + timedelta(seconds=60)),
        expected_policy_revision=1,
    )
    first = await catalog.member_page("issuer|admin", "north", q="Research person", page_size=1)
    second = await catalog.member_page("issuer|admin", "north", q="Research person", page_size=1, page=2)
    assert first["total"] == second["total"] == 2 and first["pages"] == 2
    combined = [member_dto(first["items"][0]), member_dto(second["items"][0])]
    assert {row["origin"] for row in combined} == {"manual", "corporate"}
    managed = next(row for row in combined if row["managed"])
    assert managed["source_name"] == provider.name and managed["expires_at"] is not None
    only_editor = await catalog.member_page("issuer|admin", "north", q="Research person", role="editor")
    assert only_editor["total"] == 1 and only_editor["items"][0].managed is True
    import pytest

    from koinon.catalog.errors import AccessDenied

    with pytest.raises(AccessDenied):
        await catalog.update_member("issuer|admin", "north", managed["id"], active=False)
