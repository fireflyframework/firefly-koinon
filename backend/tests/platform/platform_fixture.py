# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config

import koinon.jobs.entities  # noqa: F401 -- Register the FK target for jointly collected bulk metadata.
from koinon.catalog.entities import CatalogEntry, Membership, Tenant
from koinon.catalog.repositories import CatalogRepository, MembershipRepository, TenantRepository
from koinon.platform.authority import PlatformAccess
from koinon.platform.repositories import PlatformRepository
from koinon.tokens.authorization import TokenRestriction
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
    for cls in (PlatformAccess, PlatformRepository, PersonalTokenRepository, TokenRestriction):
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
            ("scoped", "admin", "workspace"),
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
        yield context, context.get_bean(PlatformAccess)
    finally:
        await context.stop()
