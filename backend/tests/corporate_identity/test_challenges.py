# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel import SecurityException
from pyfly.security.context import SecurityContext
from test_provider_service import identities as identities
from test_provider_service import local_input

from koinon.catalog.entities import Membership
from koinon.catalog.repositories import MembershipRepository
from koinon.corporate_identity.challenges import CorporateLoginChallenges
from koinon.corporate_identity.directory import NativeCorporateDirectory
from koinon.corporate_identity.policy import DirectorySnapshot
from koinon.corporate_identity.repositories import CorporateProviderRepository

ISSUER = "https://identity.example.test/realms/koinon"


async def test_fresh_same_account_challenge_proves_sso_and_directory_but_does_not_activate(
    identities, monkeypatch
):
    service, context = identities
    actor = ISSUER + "|admin"
    await context.get_bean(MembershipRepository).save(
        Membership(id="actual-admin", subject=actor, tenant_id="north", role="admin")
    )
    created = await service.create(actor, "north", local_input())
    challenges = context.get_bean(CorporateLoginChallenges)
    proof = await challenges.create(actor, "north", created.id, created.revision)
    assert proof.authorization_url.startswith("/oauth2/authorization/koinon?identity_test=")
    provider = await challenges.begin_authorization(proof.id, actor)
    assert provider.id == created.id

    async def acquire(*args):
        return "synthetic-directory-token"

    async def observe(settings, token, subject):
        now = datetime.now(UTC)
        return DirectorySnapshot(subject, frozenset({"group"}), True, now, now + timedelta(seconds=60))

    directory = context.get_bean(NativeCorporateDirectory)
    monkeypatch.setattr(directory, "acquire", acquire)
    monkeypatch.setattr(directory, "observe", observe)
    verified = SecurityContext(
        user_id="admin",
        attributes={"iss": ISSUER, "sub": "admin", "auth_time": int(datetime.now(UTC).timestamp())},
    )
    await challenges.complete(proof.id, verified)
    result = await challenges.get(actor, "north", created.id, proof.id)
    assert result.status == "verified" and result.authorization_url is None
    assert next(check for check in result.checks if check.id == "broker_policy").verified is True
    assert (await context.get_bean(CorporateProviderRepository).find_by_id(created.id)).status == "draft"
    with pytest.raises(SecurityException):
        await challenges.complete(proof.id, verified)


async def test_test_cannot_switch_canonical_subject_or_accept_stale_authentication(identities):
    service, context = identities
    actor = ISSUER + "|admin"
    await context.get_bean(MembershipRepository).save(
        Membership(id="actual-admin", subject=actor, tenant_id="north", role="admin")
    )
    created = await service.create(actor, "north", local_input())
    challenges = context.get_bean(CorporateLoginChallenges)
    proof = await challenges.create(actor, "north", created.id, created.revision)
    await challenges.begin_authorization(proof.id, actor)
    for sub, auth_time, code in [
        ("other", int(datetime.now(UTC).timestamp()), "IDENTITY_TEST_ACCOUNT_MISMATCH"),
        ("admin", 1, "IDENTITY_FRESH_SIGN_IN_REQUIRED"),
        ("admin", True, "IDENTITY_AUTH_TIME_REQUIRED"),
    ]:
        with pytest.raises(SecurityException) as caught:
            await challenges.complete(
                proof.id,
                SecurityContext(user_id=sub, attributes={"iss": ISSUER, "sub": sub, "auth_time": auth_time}),
            )
        assert caught.value.code == code
    assert (await challenges.get(actor, "north", created.id, proof.id)).status == "pending"
