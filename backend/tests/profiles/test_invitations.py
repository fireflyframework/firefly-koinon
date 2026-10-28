# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel import ConflictException
from test_profiles import profiles as profiles

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.invitation_repository import InvitationRepository
from koinon.catalog.invitation_service import InvitationService
from koinon.catalog.repositories import MembershipRepository
from koinon.catalog.service import CatalogService


async def test_invitation_is_hashed_one_time_and_atomic(profiles):
    _, context = profiles
    service = context.get_bean(InvitationService)
    # Test fixture identities deliberately use non-URL issuers; accepted identities use canonical URL values.
    await context.get_bean(MembershipRepository).save(
        Membership(id="inviter", subject="https://issuer.test|inviter", tenant_id="north", role="admin")
    )
    created = await service.create(
        "https://issuer.test|inviter", "north", role="editor", label="Research team"
    )
    token = created.token.get_secret_value()
    assert token not in repr(created)
    row = await context.get_bean(InvitationRepository).find_by_id(created.invitation.id)
    assert row.token_hash != token and len(row.token_hash) == 64
    preview = await service.inspect("https://issuer.test|new-person", token)
    assert preview["tenant_name"] == "north" and preview["role"] == "editor"
    member = await service.redeem("https://issuer.test|new-person", token)
    assert member.subject == "https://issuer.test|new-person" and member.role == "editor"
    with pytest.raises(AccessDenied):
        await service.redeem("https://issuer.test|another", token)
    assert (await service.page("https://issuer.test|inviter", "north", status="accepted"))["total"] == 1
    assert not any(
        "token" in key
        for key in (await service.page("https://issuer.test|inviter", "north", status="accepted"))["items"][0]
    )


async def test_expiry_revoke_revoked_inviter_issuer_and_existing_grant(profiles):
    _, context = profiles
    service = context.get_bean(InvitationService)
    catalog = context.get_bean(CatalogService)
    members = context.get_bean(MembershipRepository)
    await members.save(
        Membership(id="inviter", subject="https://issuer.test|inviter", tenant_id="north", role="admin")
    )
    created = await service.create("https://issuer.test|inviter", "north", role="viewer")
    token = created.token.get_secret_value()
    with pytest.raises(AccessDenied):
        await service.inspect("https://other.test|person", token)
    with pytest.raises(ConflictException):
        await service.redeem("https://issuer.test|inviter", token)
    assert (await service.inspect("https://issuer.test|new", token))["id"] == created.invitation.id
    await service.revoke("https://issuer.test|inviter", "north", created.invitation.id)
    with pytest.raises(AccessDenied):
        await service.redeem("https://issuer.test|new", token)
    expired = await service.create("https://issuer.test|inviter", "north", role="viewer")
    row = await context.get_bean(InvitationRepository).find_by_id(expired.invitation.id)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await context.get_bean(InvitationRepository).save(row)
    with pytest.raises(AccessDenied):
        await service.inspect("https://issuer.test|new", expired.token.get_secret_value())
    stale = await service.create("https://issuer.test|inviter", "north", role="editor")
    await catalog.update_member("issuer|admin", "north", "inviter", active=False)
    with pytest.raises(AccessDenied):
        await service.redeem("https://issuer.test|new", stale.token.get_secret_value())
    assert not await members.find_all(subject="https://issuer.test|new", tenant_id="north")


async def test_workspace_inviter_cannot_mint_organization_grants(profiles):
    _, context = profiles
    catalog = context.get_bean(CatalogService)
    workspace = await catalog.create("issuer|admin", "north", kind="workspace", name="Own")
    await context.get_bean(MembershipRepository).save(
        Membership(
            id="scoped-admin",
            subject="https://issuer.test|scoped",
            tenant_id="north",
            workspace_id=workspace.id,
            role="admin",
        )
    )
    service = context.get_bean(InvitationService)
    with pytest.raises(AccessDenied):
        await service.create("https://issuer.test|scoped", "north", role="admin")
    created = await service.create(
        "https://issuer.test|scoped", "north", workspace_id=workspace.id, role="analyst"
    )
    assert created.invitation.workspace_id == workspace.id
