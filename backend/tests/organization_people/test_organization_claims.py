# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import pytest
from organization_people_cases import A, B, C
from pyfly.kernel import ConflictException
from pyfly.security.context import SecurityContext

from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.organization_people.dtos import OrganizationPersonPatch as Patch
from koinon.organization_people.dtos import OrganizationProfileFields as Fields
from koinon.organization_people.dtos import OrganizationProfileMappingInput as Mapping


async def provider(d, tenant="north", identifier="provider"):
    row = CorporateProvider(
        id=identifier,
        tenant_id=tenant,
        kind="keycloak",
        name="Corporate directory",
        canonical_issuer="https://issuer",
        source_key=identifier,
        status="active",
        settings_json={"kind": "keycloak", "issuer": "https://issuer", "client_id": "browser"},
        created_by=A,
        updated_by=A,
    )
    await d.context.get_bean(CorporateProviderRepository).save(row)
    return row


def claims(subject="member", **values):
    return SecurityContext(user_id=subject, attributes={"iss": "https://issuer", "sub": subject, **values})


async def test_verified_claim_observation_preserves_absence_but_explicit_null_clears(directory):
    d = directory
    p = await provider(d)
    await d.service.update_mapping(
        A, "north", p.id, Mapping(expected_revision=0, enabled=True, fields=Fields(job_title="job_title"))
    )
    before = await d.catalog.permissions(B, "north", d.a)
    await d.service.observe_login(claims(job_title="Research lead"))
    row = await d.service.self(B, "north", workspace_id=d.a)
    assert (
        row.job_title == "Research lead" and row.source == "provider" and row.managed_fields == ["job_title"]
    )
    await d.service.observe_login(claims())
    missing = await d.service.self(B, "north", workspace_id=d.a)
    assert missing.job_title == "Research lead" and missing.observation_status == "unavailable"
    await d.service.observe_login(claims(job_title=None))
    cleared = await d.service.self(B, "north", workspace_id=d.a)
    assert cleared.job_title is None and cleared.observation_status == "current"
    assert await d.catalog.permissions(B, "north", d.a) == before
    actual = await d.context.get_bean(CorporateProviderRepository).find_by_id(p.id)
    assert actual.revision == 1 and actual.policy_revision == 1


async def test_manually_owned_record_is_not_overwritten_and_detach_is_explicit(directory):
    d = directory
    from koinon.organization_people.dtos import OrganizationPersonCreate

    p = await provider(d)
    await d.service.update_mapping(
        A, "north", p.id, Mapping(expected_revision=0, enabled=True, fields=Fields(job_title="job_title"))
    )
    row = await d.service.create(A, "north", OrganizationPersonCreate(subject=C, job_title="Local title"))
    await d.service.observe_login(claims("colleague", job_title="Corporate title"))
    assert (await d.service.get(A, "north", row.id)).job_title == "Local title"
    await d.service.observe_login(claims(job_title="Managed title"))
    row = await d.service.self(B, "north", workspace_id=d.a)
    with pytest.raises(ConflictException):
        await d.service.update(
            A, "north", row.id, Patch(expected_revision=row.revision, job_title="Override")
        )
    local = await d.service.update(
        A,
        "north",
        row.id,
        Patch(expected_revision=row.revision, manage_locally=True, job_title="Local choice"),
    )
    await d.service.observe_login(claims(job_title="Later corporate"))
    assert (await d.service.get(A, "north", local.id)).job_title == "Local choice"


async def test_unverified_subject_and_nonmembers_are_not_provisioned(directory):
    d = directory
    p = await provider(d)
    await d.service.update_mapping(
        A, "north", p.id, Mapping(expected_revision=0, enabled=True, fields=Fields(job_title="job_title"))
    )
    await d.service.observe_login(SecurityContext())
    await d.service.observe_login(
        SecurityContext(
            user_id="member", attributes={"iss": "https://issuer", "sub": "another", "job_title": "Invented"}
        )
    )
    await d.service.observe_login(claims("outsider", job_title="Not a member"))
    assert await d.service.people.count() == 0


async def test_multiple_active_sources_do_not_choose_first_provider(directory):
    d = directory
    for identifier in ("one", "two"):
        p = await provider(d, identifier=identifier)
        await d.service.update_mapping(
            A, "north", p.id, Mapping(expected_revision=0, enabled=True, fields=Fields(job_title="job_title"))
        )
    await d.service.observe_login(claims(job_title="Ambiguous"))
    assert await d.service.people.count() == 0


async def test_explicit_reattach_waits_for_verified_login_without_claim_input(directory):
    from koinon.organization_people.dtos import OrganizationPersonCreate

    d = directory
    p = await provider(d)
    await d.service.update_mapping(
        A, "north", p.id, Mapping(expected_revision=0, enabled=True, fields=Fields(job_title="job_title"))
    )
    row = await d.service.create(
        A, "north", OrganizationPersonCreate(subject=B, job_title="Kept while pending")
    )
    attached = await d.service.update(
        A, "north", row.id, Patch(expected_revision=1, managed_provider_id=p.id)
    )
    assert (
        attached.job_title == "Kept while pending"
        and attached.source == "provider"
        and attached.observation_status == "unavailable"
    )
    await d.service.observe_login(claims(job_title="Verified replacement"))
    assert (await d.service.get(A, "north", row.id)).job_title == "Verified replacement"


async def test_reattach_requires_both_permissions_and_active_configured_source(directory, monkeypatch):
    from koinon.catalog.errors import AccessDenied
    from koinon.organization_people.dtos import OrganizationPersonCreate

    d = directory
    p = await provider(d)
    row = await d.service.create(A, "north", OrganizationPersonCreate(subject=B))
    with pytest.raises(AccessDenied):
        await d.service.update(A, "north", row.id, Patch(expected_revision=1, managed_provider_id=p.id))
    await d.service.update_mapping(
        A, "north", p.id, Mapping(expected_revision=0, enabled=True, fields=Fields(job_title="job_title"))
    )
    original = d.catalog.authorize

    async def no_identity(actor, tenant, permission, workspace_id=None):
        if permission == "identity:manage":
            raise AccessDenied("Denied", code="ACCESS_DENIED")
        return await original(actor, tenant, permission, workspace_id)

    monkeypatch.setattr(d.catalog, "authorize", no_identity)
    with pytest.raises(AccessDenied):
        await d.service.update(A, "north", row.id, Patch(expected_revision=1, managed_provider_id=p.id))
    assert (await d.service.get(A, "north", row.id)).source == "manual"


async def test_personal_token_context_cannot_be_used_as_verified_login_attributes(directory):
    d = directory
    p = await provider(d)
    await d.service.update_mapping(
        A, "north", p.id, Mapping(expected_revision=0, enabled=True, fields=Fields(job_title="job_title"))
    )
    await d.service.observe_login(claims(job_title="Forged corporate title", koinon_token={}))
    assert await d.service.people.count() == 0


async def test_mapping_read_rechecks_admin_after_repository_await(directory, monkeypatch):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    d = directory
    p = await provider(d)
    original = d.service.mappings.scoped

    async def revoke(*args, **kwargs):
        result = await original(*args, **kwargs)
        async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
            await connection.execute(
                update(Membership)
                .where(Membership.tenant_id == "north", Membership.subject == A)
                .values(active=False)
            )
        return result

    monkeypatch.setattr(d.service.mappings, "scoped", revoke)
    with pytest.raises(AccessDenied):
        await d.service.mapping(A, "north", p.id)
