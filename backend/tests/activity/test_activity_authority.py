# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.activity.authority import ActivityAccess
from koinon.catalog.entities import CatalogEntry, Membership, Tenant
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import CatalogRepository, MembershipRepository, TenantRepository
from koinon.tokens.authorization import TokenRestriction
from koinon.tokens.entities import PersonalToken
from koinon.tokens.repositories import PersonalTokenRepository


@pytest.fixture
async def authority(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'authority.db'}",
                        }
                    },
                }
            }
        )
    )
    scan_package("koinon.catalog", context.container)
    for cls in (ActivityAccess, PersonalTokenRepository, TokenRestriction):
        context.register_bean(cls)
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        await context.get_bean(CatalogRepository).save(
            CatalogEntry(
                id="workspace",
                tenant_id="north",
                kind="workspace",
                name="Workspace",
                created_by="issuer|admin",
            )
        )
        for identifier, role, workspace in (
            ("admin", "admin", None),
            ("viewer", "viewer", None),
            ("scoped", "editor", "workspace"),
        ):
            await context.get_bean(MembershipRepository).save(
                Membership(
                    id=identifier,
                    tenant_id="north",
                    subject="issuer|" + identifier,
                    role=role,
                    workspace_id=workspace,
                )
            )
        yield context, context.get_bean(ActivityAccess)
    finally:
        await context.stop()


async def test_personal_activity_does_not_grant_organization_visibility(authority):
    _, access = authority
    assert (await access.resolve("issuer|viewer", "north", administrative=False)).workspace_ids is None
    assert (await access.resolve("issuer|scoped", "north", administrative=False)).workspace_ids == (
        "workspace",
    )
    for subject in ("issuer|viewer", "issuer|scoped", "issuer|unknown"):
        with pytest.raises(AccessDenied):
            await access.resolve(subject, "north", administrative=True)
    await access.resolve("issuer|admin", "north", administrative=True)
    with pytest.raises(AccessDenied):
        await access.resolve("issuer|admin", "south", administrative=False)


async def test_token_scope_current_membership_and_workspace_ceiling_all_apply(authority):
    context, access = authority
    token = PersonalToken(
        id="token",
        subject="issuer|admin",
        tenant_id="north",
        name="Activity",
        token_hash="a" * 64,
        prefix="token",
        scopes=["catalog:read"],
        workspace_ids=["workspace"],
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    repo = context.get_bean(PersonalTokenRepository)
    await repo.save(token)
    with SecurityContextHolder.using(
        SecurityContext(
            user_id="admin", attributes={"iss": "issuer", "sub": "admin", "koinon_token_id": "token"}
        )
    ):
        with pytest.raises(AccessDenied):
            await access.resolve("issuer|admin", "north", administrative=False)
        token.scopes = ["catalog:read", "activity:read", "audit:read"]
        await repo.save(token)
        assert (await access.resolve("issuer|admin", "north", administrative=False)).workspace_ids == (
            "workspace",
        )
        with pytest.raises(AccessDenied):
            await access.resolve("issuer|admin", "north", administrative=True)
        token.revoked_at = datetime.now(UTC)
        await repo.save(token)
        with pytest.raises(AccessDenied):
            await access.resolve("issuer|admin", "north", administrative=False)
