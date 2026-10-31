# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from corporate_profile_cases import A, B, claims, provider
from pyfly.data.relational.sqlalchemy import transactional

from koinon.corporate_profiles.dtos import CorporateProfileSyncPolicy
from koinon.organization_people.dtos import OrganizationProfileFields, OrganizationProfileMappingInput


async def configure(d, *, modern=True):
    p = await provider(d)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        OrganizationProfileMappingInput(
            expected_revision=0,
            enabled=True,
            fields=OrganizationProfileFields(job_title="title"),
            profile_sync=CorporateProfileSyncPolicy(
                job_title_source="verified_claims", unit_source="local", manager_source="local"
            )
            if modern
            else None,
        ),
    )


@pytest.mark.parametrize("modern", [True, False])
async def test_verified_bearer_first_binding_preserves_token_evidence_time_and_deduplicates_same_older_token(
    corporate, modern
):
    d = corporate
    await configure(d, modern=modern)
    evidence = datetime.now(UTC) - timedelta(minutes=2)
    context = claims(iat=evidence.timestamp(), title="Verified headless title")
    await d.sync.observe_bearer(context)

    @transactional(read_only=True)
    async def state():
        person = await d.service.people.by_subject("north", B)
        snapshot = await d.snapshots.owner("north", B)
        return (
            person.revision,
            person.job_title,
            person.observed_at,
            snapshot.binding_revision if snapshot else None,
            snapshot.claims_observed_at if snapshot else None,
        )

    before = await state()
    assert before[1] == "Verified headless title" and before[2] == evidence
    if modern:
        assert before[3] == 1 and before[4] == evidence
    await d.sync.observe_bearer(
        claims(iat=evidence.timestamp(), title="Same-token changed payload must not reapply")
    )
    await d.sync.observe_bearer(
        claims(iat=(evidence - timedelta(seconds=1)).timestamp(), title="Older evidence")
    )
    assert await state() == before
    newer = evidence + timedelta(seconds=1)
    await d.sync.observe_bearer(claims(iat=newer.timestamp(), title="New verified evidence"))
    after = await state()
    assert after[0] == before[0] + 1 and after[1] == "New verified evidence" and after[2] == newer


@pytest.mark.parametrize(
    "attributes",
    [
        {},
        {"iat": True},
        {"iat": "123"},
        {"iat": float("nan")},
        {"iat": float("inf")},
        {"iat": -1},
        {"iat": 0, "koinon_token_id": "never-bind"},
        {"iat": 0, "koinon_token": {}},
    ],
)
async def test_bearer_observer_rejects_missing_untrusted_evidence_and_personal_tokens(corporate, attributes):
    d = corporate
    await configure(d)
    await d.sync.observe_bearer(claims(title="Must not bind", **attributes))
    assert await d.service.people.count() == 0

    @transactional(read_only=True)
    async def check():
        assert await d.snapshots.owner("north", B) is None

    await check()


async def test_claims_and_personal_only_policy_does_not_request_directory_permission_or_reage_claims(
    corporate,
):
    d = corporate
    p = await provider(d)
    await d.service.update_mapping(
        A,
        "north",
        p.id,
        OrganizationProfileMappingInput(
            expected_revision=0,
            enabled=True,
            fields=OrganizationProfileFields(job_title="title"),
            profile_sync=CorporateProfileSyncPolicy(
                name_source="personal",
                avatar_source="personal",
                job_title_source="verified_claims",
                unit_source="local",
                manager_source="local",
            ),
        ),
    )
    evidence = datetime.now(UTC) - timedelta(minutes=1)
    await d.sync.observe_bearer(claims(iat=evidence.timestamp(), title="Verified title"))
    lease = (await d.refresher.claim("inert"))[0]
    assert await d.refresher.execute(lease)
    d.adapter.observe.assert_not_awaited()
    value = await d.sync.presentation(B, "north", workspace_id=d.a)
    assert next(field for field in value.fields if field.field == "job_title").observed_at == evidence
