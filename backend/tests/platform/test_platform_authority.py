# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from platform_fixture import authority as authority
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository


async def test_only_current_organization_admin_can_read_deployment_observations(authority):
    context, access = authority
    await access.resolve("issuer|admin", "north")
    for subject in ("issuer|viewer", "issuer|scoped", "issuer|unknown"):
        with pytest.raises(AccessDenied):
            await access.resolve(subject, "north")
    with pytest.raises(AccessDenied):
        await access.resolve("issuer|admin", "south")
    membership = await context.get_bean(MembershipRepository).find_by_id("admin")
    membership.active = False
    await context.get_bean(MembershipRepository).save(membership)
    with pytest.raises(AccessDenied):
        await access.resolve("issuer|admin", "north")


@pytest.mark.parametrize("restriction", ["workspace_ids", "asset_ids", "resource_ids"])
async def test_every_explicit_credential_bound_rejects_organization_observations(authority, restriction):
    context, access = authority
    token = PersonalToken(
        id="token",
        subject="issuer|admin",
        tenant_id="north",
        name="Health",
        token_hash="a" * 64,
        prefix="token",
        scopes=["catalog:read", "audit:read"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    setattr(token, restriction, [])
    await context.get_bean(PersonalTokenRepository).save(token)
    with (
        SecurityContextHolder.using(
            SecurityContext(
                user_id="admin", attributes={"iss": "issuer", "sub": "admin", "koinon_token_id": "token"}
            )
        ),
        pytest.raises(AccessDenied),
    ):
        await access.resolve("issuer|admin", "north")


async def test_audit_scope_expiry_revocation_and_membership_all_remain_current(authority):
    context, access = authority
    tokens = context.get_bean(PersonalTokenRepository)
    token = await tokens.save(
        PersonalToken(
            id="token",
            subject="issuer|admin",
            tenant_id="north",
            name="Health",
            token_hash="a" * 64,
            prefix="token",
            scopes=["catalog:read"],
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    with SecurityContextHolder.using(
        SecurityContext(
            user_id="admin", attributes={"iss": "issuer", "sub": "admin", "koinon_token_id": "token"}
        )
    ):
        with pytest.raises(AccessDenied):
            await access.resolve("issuer|admin", "north")
        token.scopes = ["catalog:read", "audit:read"]
        await tokens.save(token)
        first = await access.resolve("issuer|admin", "north")
        assert first.fingerprint
        token.revoked_at = datetime.now(UTC)
        await tokens.save(token)
        with pytest.raises(AccessDenied):
            await access.resolve("issuer|admin", "north")
