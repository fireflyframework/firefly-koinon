# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import InvalidRequestException
from test_profiles import profiles as profiles

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository
from koinon.catalog.service import CatalogService


async def test_membership_pages_filter_names_roles_and_scope_in_sql(profiles):
    profile, context = profiles
    service = context.get_bean(CatalogService)
    await profile.update("issuer|member", {"display_name": "Named researcher"})
    workspace = await service.create("issuer|admin", "north", kind="workspace", name="Research")
    await context.get_bean(MembershipRepository).save(
        Membership(
            id="scoped", subject="issuer|member", tenant_id="north", workspace_id=workspace.id, role="editor"
        )
    )
    page = await service.member_page("issuer|admin", "north", q="researcher", page_size=1)
    assert page["total"] == 2 and page["pages"] == 2 and len(page["items"]) == 1
    second = await service.member_page("issuer|admin", "north", q="researcher", page_size=1, page=2)
    assert second["items"][0].id != page["items"][0].id
    scoped = await service.member_page(
        "issuer|admin", "north", scope="workspace", workspace_id=workspace.id, role="editor"
    )
    assert scoped["total"] == 1 and scoped["items"][0].id == "scoped"
    tenant = await service.member_page("issuer|admin", "north", scope="tenant")
    assert tenant["total"] == 2 and all(row.workspace_id is None for row in tenant["items"])
    assert (await service.member_page("issuer|admin", "north", q="%"))["total"] == 0
    with pytest.raises(AccessDenied):
        await service.member_page("issuer|member", "north")
    with pytest.raises(AccessDenied):
        await service.member_page("issuer|admin", "south")
    for values in (
        {"page_size": 101},
        {"page": 0},
        {"scope": "invalid"},
        {"role": "owner"},
        {"scope": "workspace"},
    ):
        with pytest.raises(InvalidRequestException):
            await service.member_page("issuer|admin", "north", **values)
