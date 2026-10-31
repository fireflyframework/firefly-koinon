# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from corporate_profile_cases import A, B, C, claims, provider
from pyfly.kernel import ConflictException, ResourceNotFoundException

from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy as Policy
from koinon.corporate_profiles.dtos import OrganizationPresentationInput
from koinon.corporate_profiles.normalization import DirectoryProfileObservation, FieldObservation
from koinon.organization_people.dtos import OrganizationProfileFields as Fields
from koinon.organization_people.dtos import OrganizationProfileMappingInput as Mapping


async def configured(d, *, policy=None, fields=None):
    p = await provider(d)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        Mapping(
            expected_revision=0,
            enabled=True,
            fields=fields or Fields(),
            profile_sync=policy
            or Policy(manager_source="local", unit_source="local", job_title_source="local"),
        ),
    )
    await d.sync.observe_login(claims())
    return p


async def publish(d, name="Company member", avatar=None):
    leases = await d.refresher.claim("inert", limit=2)
    assert len(leases) == 1
    ticket = await d.refresher.prepare(leases[0])
    assert ticket is not None
    observation = DirectoryProfileObservation(
        "member",
        {
            "display_name": FieldObservation("current", name),
            "avatar": FieldObservation("current", avatar) if avatar else FieldObservation("empty"),
        },
    )
    assert await d.refresher.commit(ticket, observation)
    return ticket


async def test_overlay_never_mutates_personal_or_other_tenant_and_get_creates_no_position(corporate):
    d = corporate
    await configured(d)
    original = await d.profiles.get(B)
    await publish(d)
    view = await d.sync.presentation(B, "north", workspace_id=d.a)
    assert view.display_name == "Company member" and view.name_source == "organization"
    assert (await d.profiles.get(B)) == original
    assert (await d.service.self(B, "north", workspace_id=d.a)).display_name == "Company member"
    assert (await d.service.self(B, "south")).display_name == "Member"
    assert await d.service.people.count() == 0


async def test_preferences_revision_and_disable_preserve_personal(corporate):
    d = corporate
    p = await configured(d)
    await publish(d)
    result = await d.sync.update_presentation(
        B, "north", OrganizationPresentationInput(expected_revision=0, name_mode="personal"), workspace_id=d.a
    )
    assert result.display_name == "Member" and result.revision == 1
    with pytest.raises(ConflictException):
        await d.sync.update_presentation(
            B,
            "north",
            OrganizationPresentationInput(expected_revision=0, name_mode="organization"),
            workspace_id=d.a,
        )
    current = await d.service.mapping(A, "north", p.id)
    # Old wire requests preserve the new policy rather than silently disabling it.
    kept = await d.service.update_mapping(
        A, "north", p.id, Mapping(expected_revision=current.revision, enabled=True, fields=Fields())
    )
    assert kept.profile_sync is not None
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        Mapping(expected_revision=kept.revision, enabled=True, fields=Fields(), profile_sync=None),
    )
    assert (await d.sync.presentation(B, "north", workspace_id=d.a)).name_source == "personal"


async def test_verified_claim_status_is_genuine_and_survives_periodic_observation(corporate):
    d = corporate
    await configured(
        d,
        policy=Policy(job_title_source="verified_claims", unit_source="local", manager_source="local"),
        fields=Fields(job_title="title"),
    )
    await d.service.observe_login(claims(title="Engineer"))
    before = await d.sync.presentation(B, "north", workspace_id=d.a)
    field = next(item for item in before.fields if item.field == "job_title")
    assert field.status == "current" and field.observed_at is not None
    await publish(d)
    after = await d.sync.presentation(B, "north", workspace_id=d.a)
    assert next(item for item in after.fields if item.field == "job_title").observed_at == field.observed_at
    assert after.status == "current"


@pytest.mark.parametrize("change", ["mapping", "membership", "preference", "binding", "lease"])
async def test_observation_fences_stale_work(corporate, change):
    from pyfly.data.relational.sqlalchemy import transactional

    d = corporate
    p = await configured(d)
    lease = (await d.refresher.claim("inert"))[0]
    ticket = await d.refresher.prepare(lease)

    @transactional
    async def alter():
        if change == "mapping":
            row = await d.service.mappings.scoped("north", p.id)
            row.enabled = False
            await d.service.mappings.save(row)
        elif change == "membership":
            row = await d.memberships.find_by_id("m-0")
            row.active = False
            await d.memberships.save(row)
        elif change == "preference":
            from koinon.corporate_profiles.entities import OrganizationPresentationPreference

            await d.preferences.save(
                OrganizationPresentationPreference(
                    tenant_id="north", subject=B, name_mode="personal", avatar_mode="personal"
                )
            )
        else:
            row = await d.snapshots.owner("north", B)
            if change == "binding":
                row.binding_revision += 1
            else:
                row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
            await d.snapshots.save(row)

    await alter()
    assert not await d.refresher.commit(
        ticket,
        DirectoryProfileObservation(
            "member", {"display_name": FieldObservation("current", "Must not publish")}
        ),
    )

    @transactional(read_only=True)
    async def check():
        row = await d.snapshots.owner("north", B)
        assert row.display_name is None

    await check()


async def test_disabled_provider_blanks_corporate_mode_without_legacy_personal_fallback(corporate):
    d = corporate
    p = await configured(d)
    await publish(d)
    from koinon.corporate_identity.repositories import CorporateProviderRepository

    row = await d.context.get_bean(CorporateProviderRepository).find_by_id(p.id)
    row.status = "disabled"
    await d.context.get_bean(CorporateProviderRepository).save(row)
    result = await d.sync.presentation(B, "north", workspace_id=d.a)
    assert (
        result.display_name == "" and result.name_source == "organization" and result.status == "unavailable"
    )
    with pytest.raises(ResourceNotFoundException):
        await d.service.avatar(B, "north", result.profile_id, workspace_id=d.a)


async def test_disabled_policy_is_sql_null_and_never_leased(corporate):
    d = corporate
    p = await configured(d)
    current = await d.service.mapping(A, "north", p.id)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        Mapping(expected_revision=current.revision, enabled=True, fields=Fields(), profile_sync=None),
    )
    assert await d.refresher.claim("inert") == []


async def test_duplicate_external_binding_never_steals_first_user_or_applies_claims(corporate):
    from pyfly.data.relational.sqlalchemy import transactional

    from koinon.corporate_identity.repositories import CorporateProviderRepository

    d = corporate
    p = await provider(d)
    p.broker_alias = "corporate"
    await d.context.get_bean(CorporateProviderRepository).save(p)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        Mapping(
            expected_revision=0,
            enabled=True,
            fields=Fields(job_title="title"),
            profile_sync=Policy(job_title_source="verified_claims"),
        ),
    )

    def login(user, title):
        return claims(
            user, koinon_identity_provider="corporate", koinon_external_subject="one-external-id", title=title
        )

    await d.sync.observe_login(login("member", "First title"))
    await d.service.observe_login(login("member", "First title"))
    await d.sync.observe_login(login("colleague", "Must not transfer"))
    await d.service.observe_login(login("colleague", "Must not transfer"))

    @transactional(read_only=True)
    async def check():
        first = await d.snapshots.owner("north", B)
        second = await d.snapshots.owner("north", C)
        assert (
            first.provider_id == p.id
            and first.external_subject == "one-external-id"
            and first.status != "conflict"
        )
        assert second.status == "conflict" and second.provider_id is None and second.external_subject is None
        assert (await d.service.people.by_subject("north", B)).job_title == "First title"
        assert await d.service.people.by_subject("north", C) is None

    await check()


async def test_policy_and_personal_override_are_tenant_bound(corporate):
    d = corporate
    await configured(
        d,
        policy=Policy(
            allow_personal_overrides=False,
            manager_source="local",
            unit_source="local",
            job_title_source="local",
        ),
    )
    await publish(d)
    with pytest.raises(ConflictException):
        await d.sync.update_presentation(
            B,
            "north",
            OrganizationPresentationInput(expected_revision=0, name_mode="personal"),
            workspace_id=d.a,
        )
    south = await d.sync.update_presentation(
        B, "south", OrganizationPresentationInput(expected_revision=0, name_mode="personal")
    )
    assert south.name_source == "personal" and south.display_name == "Member"
    assert (await d.sync.presentation(B, "north", workspace_id=d.a)).revision == 0


async def test_self_avatar_does_not_open_private_directory_and_author_projection_is_batched(corporate):
    from koinon.catalog.errors import AccessDenied

    d = corporate
    await configured(d)
    await publish(d, avatar=b"already sanitized test bytes")
    view = await d.sync.presentation(B, "north", workspace_id=d.a)
    assert (
        await d.service.avatar(B, "north", view.profile_id, workspace_id=d.a)
        == b"already sanitized test bytes"
    )
    with pytest.raises(AccessDenied):
        await d.service.avatar(C, "north", view.profile_id, workspace_id=d.a)
    authors = await d.profiles.author_summaries({B}, actor=A, tenant_id="north")
    assert authors[B]["display_name"] == "Company member"
    assert "data:image/jpeg;base64," in authors[B]["avatar_data_url"]


async def test_directory_filter_uses_effective_company_name_and_hides_disabled_personal_name(corporate):
    d = corporate
    p = await configured(d)
    await publish(d, name="Corporate unique")
    assert (await d.service.page(A, "north", q="Corporate unique")).total == 1
    assert (await d.service.page(A, "north", q="Member")).total == 0
    from koinon.corporate_identity.repositories import CorporateProviderRepository

    p.status = "disabled"
    await d.context.get_bean(CorporateProviderRepository).save(p)
    assert (await d.service.page(A, "north", q="Member")).total == 0


async def test_manual_refresh_cannot_reopen_bound_conflict(corporate):
    from pyfly.data.relational.sqlalchemy import transactional

    d = corporate
    await configured(d)
    await publish(d)

    @transactional
    async def ambiguous():
        row = await d.snapshots.owner("north", B)
        row.status = "conflict"
        await d.snapshots.save(row)

    await ambiguous()
    queued = await d.sync.refresh_self(B, "north", workspace_id=d.a)
    assert queued.status == "conflict"
    assert await d.refresher.claim("inert") == []
    assert (await d.sync.presentation(B, "north", workspace_id=d.a)).display_name == ""


async def test_expired_worker_cannot_publish_over_reclaimed_lease(corporate):
    from pyfly.data.relational.sqlalchemy import transactional

    d = corporate
    await configured(d)
    old = (await d.refresher.claim("old"))[0]
    ticket = await d.refresher.prepare(old)

    @transactional
    async def expire():
        row = await d.snapshots.owner("north", B)
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
        await d.snapshots.save(row)

    await expire()
    new = (await d.refresher.claim("new"))[0]
    assert new.generation > old.generation
    assert not await d.refresher.commit(
        ticket,
        DirectoryProfileObservation("member", {"display_name": FieldObservation("current", "Old worker")}),
    )
    await d.refresher.failed(old, "PROFILE_REFRESH_UNAVAILABLE")
    fresh = await d.refresher.prepare(new)
    assert fresh is not None and fresh.lease.worker_id == "new"


@pytest.mark.parametrize("outcome", ["success", "failure"])
async def test_inflight_worker_cannot_resolve_new_login_conflict(corporate, outcome):
    from pyfly.data.relational.sqlalchemy import transactional

    from koinon.corporate_profiles.service import mark_conflict

    d = corporate
    await configured(d)
    await publish(d)
    await d.sync.refresh_self(B, "north", workspace_id=d.a)
    lease = (await d.refresher.claim("inert"))[0]
    ticket = await d.refresher.prepare(lease)

    @transactional
    async def ambiguous():
        row = await d.snapshots.owner("north", B)
        mark_conflict(row)
        await d.snapshots.save(row)

    await ambiguous()
    if outcome == "success":
        assert not await d.refresher.commit(
            ticket,
            DirectoryProfileObservation(
                "member", {"display_name": FieldObservation("current", "Must remain hidden")}
            ),
        )
    else:
        await d.refresher.failed(lease, "PROFILE_REFRESH_UNAVAILABLE")
    result = await d.sync.presentation(B, "north", workspace_id=d.a)
    assert result.status == "conflict" and result.display_name == "" and result.avatar_url is None
    assert await d.refresher.claim("new") == []


async def test_fetch_and_image_sanitization_run_outside_primary_transaction_and_retain_personal(corporate):
    from io import BytesIO
    from unittest.mock import AsyncMock

    from PIL import Image
    from pyfly.data.transaction import current_unit_of_work

    d = corporate
    await configured(d)
    original = await d.profiles.get(B)
    buffer = BytesIO()
    Image.new("RGBA", (300, 200), (0, 120, 200, 100)).save(buffer, format="PNG")

    async def observe(*args):
        assert current_unit_of_work("primary") is None
        return DirectoryProfileObservation(
            "member",
            {
                "display_name": FieldObservation("current", "Verified company"),
                "avatar": FieldObservation("current", buffer.getvalue()),
            },
        )

    d.adapter.observe = AsyncMock(side_effect=observe)
    lease = (await d.refresher.claim("inert"))[0]
    assert await d.refresher.execute(lease)
    value = await d.sync.presentation(B, "north", workspace_id=d.a)
    assert value.display_name == "Verified company" and value.avatar_version
    content = await d.service.avatar(B, "north", value.profile_id, workspace_id=d.a)
    image = Image.open(BytesIO(content))
    assert image.format == "JPEG" and max(image.size) <= 128 and len(content) <= 65536
    assert await d.profiles.get(B) == original


async def test_avatar_conditional_get_reauthorizes_current_scope(corporate):
    from hashlib import sha256

    from pyfly.data.relational.sqlalchemy import transactional
    from starlette.requests import Request

    from koinon.catalog.errors import AccessDenied
    from koinon.organization_people.controllers import OrganizationPeopleController

    d = corporate
    await configured(d)
    await publish(d, avatar=b"inert sanitized JPEG")
    value = await d.sync.presentation(B, "north", workspace_id=d.a)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/tenants/north/organization/people/person/avatar",
            "headers": [
                (b"if-none-match", ('"' + sha256(b"inert sanitized JPEG").hexdigest() + '"').encode())
            ],
        }
    )
    request.state.security_context = claims()
    controller = OrganizationPeopleController(d.service)
    assert (await controller.avatar("north", value.profile_id, request, workspace_id=d.a)).status_code == 304

    @transactional
    async def revoke():
        row = await d.memberships.find_by_id("m-0")
        row.active = False
        await d.memberships.save(row)

    await revoke()
    with pytest.raises(AccessDenied):
        await controller.avatar("north", value.profile_id, request, workspace_id=d.a)


async def test_final_presentation_read_detects_membership_departure_after_initial_owner_check(
    corporate, monkeypatch
):
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from sqlalchemy import update

    from koinon.catalog.entities import Membership
    from koinon.catalog.errors import AccessDenied

    d = corporate
    await configured(d)
    await publish(d)
    original = d.sync._owner

    async def revoke(*args, **kwargs):
        await original(*args, **kwargs)
        async with d.context.get_bean(DataSourceRegistry).primary.engine.begin() as connection:
            await connection.execute(
                update(Membership)
                .where(Membership.subject == B, Membership.tenant_id == "north")
                .values(active=False)
            )

    monkeypatch.setattr(d.sync, "_owner", revoke)
    with pytest.raises(AccessDenied):
        await d.sync.presentation(B, "north", workspace_id=d.a)


@pytest.mark.parametrize("changes", ["scope", "workspace", "asset", "revoked", "other_tenant"])
async def test_personal_token_requires_current_persisted_profile_scope_and_bounds(corporate, changes):
    from pyfly.data.relational.sqlalchemy import transactional
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder

    from koinon.catalog.errors import AccessDenied
    from koinon.tokens.entities import PersonalToken

    d = corporate
    await configured(d)

    @transactional
    async def create():
        row = PersonalToken(
            id="inert",
            subject=B,
            tenant_id="south" if changes == "other_tenant" else "north",
            name="Inert",
            token_hash="0" * 64,
            prefix="inert",
            scopes=["catalog:read"] if changes == "scope" else ["profile:write"],
            workspace_ids=[d.b] if changes == "workspace" else [d.a],
            asset_ids=["asset"] if changes == "asset" else None,
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
            revoked_at=datetime.now(UTC) if changes == "revoked" else None,
        )
        d.snapshots._require_session().add(row)
        await d.snapshots._require_session().flush()

    await create()
    context = SecurityContext(
        user_id="member",
        attributes={
            "iss": "https://issuer",
            "sub": "member",
            "koinon_token": {
                "id": "inert",
                "scopes": ["profile:write"],
                "tenant_id": "north",
                "workspace_ids": [d.a],
            },
        },
    )
    with SecurityContextHolder.using(context), pytest.raises(AccessDenied):
        await d.sync.presentation(B, "north", workspace_id=d.a)


async def test_admin_refresh_requires_tenant_admin_and_cannot_create_other_person_assignment(corporate):
    from corporate_profile_cases import S, W

    from koinon.catalog.errors import AccessDenied
    from koinon.profiles.service import profile_id

    d = corporate
    await configured(d)
    with pytest.raises(AccessDenied):
        await d.sync.refresh_person(W, "north", profile_id(B), workspace_id=d.a)
    with pytest.raises(AccessDenied):
        await d.sync.refresh_person(A, "north", profile_id(S))
    result = await d.sync.refresh_person(A, "north", profile_id(C))
    assert result.status == "not_bound" and await d.service.people.count() == 0


async def test_personal_token_profile_write_can_refresh_self_but_not_admin_route(corporate):
    from pyfly.data.relational.sqlalchemy import transactional
    from pyfly.security.context import SecurityContext
    from pyfly.security.context_holder import SecurityContextHolder
    from starlette.requests import Request

    from koinon.catalog.errors import AccessDenied
    from koinon.corporate_profiles.controllers import CorporateProfilesController
    from koinon.corporate_profiles.dtos import CorporateProfileRefreshInput
    from koinon.profiles.service import profile_id
    from koinon.tokens.entities import PersonalToken

    d = corporate
    await configured(d)

    @transactional
    async def create():
        row = PersonalToken(
            id="inert",
            subject=B,
            tenant_id="north",
            name="Inert",
            token_hash="0" * 64,
            prefix="inert",
            scopes=["profile:write"],
            workspace_ids=[d.a],
            expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        d.snapshots._require_session().add(row)
        await d.snapshots._require_session().flush()

    await create()
    context = SecurityContext(
        user_id="member",
        attributes={
            "iss": "https://issuer",
            "sub": "member",
            "koinon_token": {
                "id": "inert",
                "scopes": ["profile:write"],
                "tenant_id": "north",
                "workspace_ids": [d.a],
            },
        },
    )
    with SecurityContextHolder.using(context):
        assert (await d.sync.refresh_self(B, "north", workspace_id=d.a)).status == "queued"
        assert (await d.sync.presentation(B, "north", workspace_id=d.a)).name_source == "organization"
    request = Request(
        {
            "type": "http",
            "path": "/api/v1/tenants/north/organization/people/person/profile-refresh",
            "method": "POST",
            "headers": [],
        }
    )
    request.state.security_context = context
    with pytest.raises(AccessDenied):
        await CorporateProfilesController(d.sync).refresh_person(
            "north", profile_id(B), CorporateProfileRefreshInput(), request, workspace_id=d.a
        )


async def test_position_write_response_uses_same_effective_name_as_read(corporate):
    from koinon.organization_people.dtos import OrganizationPersonCreate, OrganizationPersonPatch

    d = corporate
    await configured(d)
    await publish(d)
    created = await d.service.create(
        A,
        "north",
        OrganizationPersonCreate(
            profile_id=(await d.sync.presentation(B, "north", workspace_id=d.a)).profile_id,
            job_title="Local title",
        ),
    )
    assert created.display_name == "Company member" and created.presentation.name_source == "organization"
    changed = await d.service.update(
        A,
        "north",
        created.id,
        OrganizationPersonPatch(expected_revision=created.revision, job_title="Revised title"),
    )
    assert changed.display_name == "Company member" and changed.presentation.name_source == "organization"


async def test_directory_only_policy_supports_explicit_reattach_and_immediate_local_field_ownership(
    corporate,
):
    from koinon.organization_people.dtos import OrganizationPersonCreate, OrganizationPersonPatch

    d = corporate
    p = await configured(d)
    person = await d.service.create(A, "north", OrganizationPersonCreate(subject=B, job_title="Local title"))
    attached = await d.service.update(
        A,
        "north",
        person.id,
        OrganizationPersonPatch(expected_revision=person.revision, managed_provider_id=p.id),
    )
    assert attached.provider_id == p.id
    current = await d.service.mapping(A, "north", p.id)
    current = await d.service.update_mapping(
        A,
        "north",
        p.id,
        Mapping(
            expected_revision=current.revision,
            enabled=True,
            fields=Fields(),
            profile_sync=Policy(job_title_source="directory", manager_source="local", unit_source="local"),
        ),
    )
    with pytest.raises(ConflictException):
        await d.service.update(
            A,
            "north",
            person.id,
            OrganizationPersonPatch(expected_revision=attached.revision, job_title="Blocked"),
        )
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        Mapping(
            expected_revision=current.revision,
            enabled=True,
            fields=Fields(),
            profile_sync=Policy(job_title_source="local", manager_source="local", unit_source="local"),
        ),
    )
    assert "job_title" not in (await d.service.get(A, "north", person.id)).managed_fields
    changed = await d.service.update(
        A,
        "north",
        person.id,
        OrganizationPersonPatch(expected_revision=attached.revision, job_title="Owned locally"),
    )
    assert changed.job_title == "Owned locally" and "job_title" not in changed.managed_fields


async def test_admitted_author_and_admin_picker_share_corporate_name_and_bytes_even_with_private_directory(
    corporate,
):
    d = corporate
    await configured(d)
    await d.profiles.update(B, {"display_name": "Private secondary alias"})
    await publish(d, avatar=b"inert sanitized company JPEG")
    authors = await d.profiles.author_summaries({B}, actor=C, tenant_id="north", workspace_id=d.a)
    assert authors[B]["display_name"] == "Company member"
    assert set(authors[B]) == {"subject", "display_name", "avatar_data_url", "avatar_version"}
    assert authors[B]["avatar_data_url"]
    picker = await d.profiles.people(A, "north", q="Company member")
    assert len(picker["items"]) == 1
    assert picker["items"][0]["display_name"] == "Company member"
    assert "/people/" in picker["items"][0]["avatar_url"]
    assert (
        await d.profiles.directory_avatar(A, "north", picker["items"][0]["profile_id"])
        == b"inert sanitized company JPEG"
    )
    assert (await d.profiles.people(A, "north", q="Private secondary alias"))["items"] == []


async def test_membership_and_audit_name_filters_follow_effective_tenant_presentation(corporate):
    from pyfly.data.relational.sqlalchemy import transactional

    d = corporate
    await d.profiles.update(B, {"display_name": "Private unique personal alias"})
    await configured(d)
    await publish(d, name="Company unique directory name")
    assert (await d.catalog.member_page(A, "north", q="Private unique personal alias"))["total"] == 0
    assert (await d.catalog.member_page(A, "north", q="Company unique directory name"))["total"] == 1

    @transactional
    async def audit():
        await d.catalog._audit(B, "north", "test.company.presentation", "inert", {})

    await audit()
    assert (await d.catalog.audit_page(A, "north", q="Private unique personal alias"))["total"] == 0
    assert (await d.catalog.audit_page(A, "north", q="Company unique directory name"))["total"] >= 1
