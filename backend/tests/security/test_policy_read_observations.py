# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read observations must not become grants across time, credentials, or writes."""

from datetime import UTC, datetime, timedelta

import pytest
from pyfly.data.transaction import TransactionTemplate
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import update
from test_primary_authority import ISSUER, NOW, SUBJECT, TOKEN_ID
from test_primary_authority import authority as authority

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.corporate_identity.entities import CorporateGrant, CorporateMapping, CorporateProvider
from koinon.security.authority import primary_authority
from koinon.tokens.entities import PersonalToken


async def test_cached_memberships_still_apply_the_current_token(authority):
    authority.catalog.restriction = authority.restriction
    async with TransactionTemplate("primary").transaction() as writer:
        await writer.resource.execute(update(Membership).values(active=True))
        await writer.resource.execute(
            update(PersonalToken)
            .where(PersonalToken.id == TOKEN_ID)
            .values(revoked_at=None, scopes=["catalog:read"])
        )
    with pytest.raises(AccessDenied):
        async with primary_authority():
            await authority.catalog.authorize(SUBJECT, "tenant", "members:write")
            with SecurityContextHolder.using(
                SecurityContext(
                    user_id="principal",
                    attributes={"iss": ISSUER, "sub": "principal", "koinon_token_id": TOKEN_ID},
                )
            ):
                await authority.catalog.authorize(SUBJECT, "tenant", "members:write")


async def test_managed_membership_expiry_is_checked_even_in_a_fixed_snapshot(authority, monkeypatch):
    async with TransactionTemplate("primary").transaction() as writer:
        await writer.resource.execute(update(CorporateProvider).values(status="active"))
        await writer.resource.execute(update(CorporateMapping).values(enabled=True))
        await writer.resource.execute(update(CorporateGrant).values(active=True))

    class Later(datetime):
        @classmethod
        def now(cls, tz=UTC):
            return NOW + timedelta(hours=2)

    with pytest.raises(AccessDenied):
        async with primary_authority():
            await authority.managed.authorize(SUBJECT, "tenant", "identity:manage")
            monkeypatch.setattr("koinon.catalog.service.datetime", Later)
            await authority.managed.authorize(SUBJECT, "tenant", "identity:manage")


async def test_writer_observes_membership_changes_within_its_own_transaction(authority):
    async with TransactionTemplate("primary").transaction() as writer:
        await writer.resource.execute(update(Membership).values(active=True))
        assert len(await authority.catalog.memberships(SUBJECT)) == 1
        await writer.resource.execute(update(Membership).values(active=False))
        assert await authority.catalog.memberships(SUBJECT) == []
