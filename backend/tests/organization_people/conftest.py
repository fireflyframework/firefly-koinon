# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from organization_people_cases import A, B, C, H, S, W
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.profiles.service import ProfileService


@pytest.fixture
async def directory(tmp_path):
    from koinon.organization_people.service import OrganizationPeopleService

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'directory.db'}",
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.profiles", "koinon.organization_people"):
        scan_package(package, context.container)
    from koinon.corporate_identity.repositories import CorporateProviderRepository

    context.container.register(CorporateProviderRepository)
    await context.start()
    try:
        tenants = context.get_bean(TenantRepository)
        for tenant in ("north", "south"):
            await tenants.save(Tenant(id=tenant, name=tenant))
        memberships = context.get_bean(MembershipRepository)
        for subject, tenant, workspace, role in ((A, "north", None, "admin"), (S, "south", None, "admin")):
            await memberships.save(
                Membership(id=subject, subject=subject, tenant_id=tenant, workspace_id=workspace, role=role)
            )
        catalog = context.get_bean(CatalogService)
        wa = await catalog.create(A, "north", kind="workspace", name="Shared")
        wb = await catalog.create(A, "north", kind="workspace", name="Private")
        for index, (subject, tenant, workspace, role) in enumerate(
            (
                (B, "north", wa.id, "viewer"),
                (C, "north", wa.id, "viewer"),
                (H, "north", wb.id, "viewer"),
                (W, "north", wa.id, "admin"),
                (B, "south", None, "viewer"),
            )
        ):
            await memberships.save(
                Membership(
                    id=f"m-{index}", subject=subject, tenant_id=tenant, workspace_id=workspace, role=role
                )
            )
        profiles = context.get_bean(ProfileService)
        for subject, name in (
            (A, "Administrator"),
            (B, "Member"),
            (C, "Colleague"),
            (H, "Private person"),
            (W, "Workspace admin"),
            (S, "South admin"),
        ):
            await profiles.update(subject, {"display_name": name})
        yield SimpleNamespace(
            service=context.get_bean(OrganizationPeopleService),
            context=context,
            catalog=catalog,
            profiles=profiles,
            memberships=memberships,
            a=wa.id,
            b=wb.id,
        )
    finally:
        await context.stop()
