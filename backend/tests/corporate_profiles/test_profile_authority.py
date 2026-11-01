# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from corporate_profile_cases import A, C, claims, provider

from koinon.corporate_identity.repositories import CorporateProviderRepository
from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy
from koinon.organization_people.dtos import OrganizationProfileFields, OrganizationProfileMappingInput


async def test_unbound_duplicate_binding_does_not_publish_personal_name_under_enforced_corporate_policy(
    corporate,
):
    d = corporate
    p = await provider(d)
    p.broker_alias = "corporate"
    await d.context.get_bean(CorporateProviderRepository).save(p)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        OrganizationProfileMappingInput(
            expected_revision=0,
            enabled=True,
            fields=OrganizationProfileFields(),
            profile_sync=CorporateProfileSyncPolicy(
                allow_personal_overrides=False,
                job_title_source="local",
                unit_source="local",
                manager_source="local",
            ),
        ),
    )
    await d.profiles.update(C, {"display_name": "Personal name from another organization"})
    await d.sync.observe_login(
        claims("member", koinon_identity_provider="corporate", koinon_external_subject="external-one")
    )
    await d.sync.observe_login(
        claims("colleague", koinon_identity_provider="corporate", koinon_external_subject="external-one")
    )
    view = await d.sync.presentation(C, "north", workspace_id=d.a)
    assert view.status == "conflict"
    assert view.name_source == "organization"
    assert view.display_name == ""


async def test_author_projection_never_falls_back_to_personal_name_when_company_policy_is_enforced(corporate):
    from corporate_profile_cases import B

    d = corporate
    p = await provider(d)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        OrganizationProfileMappingInput(
            expected_revision=0,
            enabled=True,
            fields=OrganizationProfileFields(),
            profile_sync=CorporateProfileSyncPolicy(
                allow_personal_overrides=False,
                job_title_source="local",
                unit_source="local",
                manager_source="local",
            ),
        ),
    )
    await d.profiles.update(C, {"display_name": "Private personal name outside company presentation"})
    await d.sync.observe_login(claims("colleague"))
    owner = await d.sync.presentation(C, "north", workspace_id=d.a)
    assert owner.name_source == "organization" and owner.display_name == ""
    authors = await d.profiles.author_summaries({C}, actor=B, tenant_id="north", workspace_id=d.a)
    assert authors[C]["display_name"] != "Private personal name outside company presentation"


async def test_tenant_author_projection_does_not_return_other_tenant_personal_profile(corporate):
    from corporate_profile_cases import S

    d = corporate
    await d.profiles.update(S, {"display_name": "Private current name from South"})
    authors = await d.profiles.author_summaries({S}, actor=A, tenant_id="north", workspace_id=d.a)
    assert authors[S]["display_name"] != "Private current name from South"


async def test_system_author_survives_corporate_projection_without_guessing_other_authors(corporate):
    d = corporate
    subjects = {"system:installation", "system:other", "issuer|system:installation"}
    authors = await d.profiles.author_summaries(subjects, actor=A, tenant_id="north", workspace_id=d.a)
    assert authors["system:installation"]["display_name"] == "koinon"
    assert authors["system:other"]["display_name"] == ""
    assert authors["issuer|system:installation"]["display_name"] == ""


async def test_disabling_policy_hides_retained_unbound_conflict_and_resumes_personal(corporate):
    d = corporate
    p = await provider(d)
    p.broker_alias = "corporate"
    await d.context.get_bean(CorporateProviderRepository).save(p)
    mapping = await d.service.update_mapping(
        A,
        "north",
        p.id,
        OrganizationProfileMappingInput(
            expected_revision=0,
            enabled=True,
            fields=OrganizationProfileFields(),
            profile_sync=CorporateProfileSyncPolicy(allow_personal_overrides=False),
        ),
    )
    await d.sync.observe_login(
        claims("member", koinon_identity_provider="corporate", koinon_external_subject="one")
    )
    await d.sync.observe_login(
        claims("colleague", koinon_identity_provider="corporate", koinon_external_subject="one")
    )
    view = await d.sync.presentation(C, "north", workspace_id=d.a)
    assert (
        view.status == "conflict" and view.name_source == "organization" and not view.allow_personal_overrides
    )
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        OrganizationProfileMappingInput(
            expected_revision=mapping.revision,
            enabled=True,
            fields=OrganizationProfileFields(),
            profile_sync=None,
        ),
    )
    view = await d.sync.presentation(C, "north", workspace_id=d.a)
    assert (
        view.status == "not_configured"
        and view.name_source == "personal"
        and view.display_name == "Colleague"
    )


async def test_unbound_conflict_cannot_save_personal_override_under_enforced_policy(corporate):
    import pytest
    from pyfly.kernel import ConflictException

    from koinon.corporate_profiles.dtos import OrganizationPresentationInput

    d = corporate
    p = await provider(d)
    p.broker_alias = "corporate"
    await d.context.get_bean(CorporateProviderRepository).save(p)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        OrganizationProfileMappingInput(
            expected_revision=0,
            enabled=True,
            fields=OrganizationProfileFields(),
            profile_sync=CorporateProfileSyncPolicy(allow_personal_overrides=False),
        ),
    )
    await d.sync.observe_login(
        claims("member", koinon_identity_provider="corporate", koinon_external_subject="one")
    )
    await d.sync.observe_login(
        claims("colleague", koinon_identity_provider="corporate", koinon_external_subject="one")
    )
    with pytest.raises(ConflictException):
        await d.sync.update_presentation(
            C,
            "north",
            OrganizationPresentationInput(expected_revision=0, name_mode="personal"),
            workspace_id=d.a,
        )
    view = await d.sync.presentation(C, "north", workspace_id=d.a)
    assert view.revision == 0 and view.display_name == "" and not view.allow_personal_overrides
