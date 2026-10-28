# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from conftest import ISSUER, bearer
from pydantic import BaseModel
from pyfly.container import rest_controller
from pyfly.web import Body, Valid, post_mapping, request_mapping
from starlette.requests import Request

pytest.importorskip("flycanon")
from flycanon.web.conventions import tenant_context_from_request
from flycanon.web.conventions.context import current_tenant_context

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.web.legacy_security import LegacyOperationPolicies


class Link(BaseModel):
    source_id: str
    target_id: str


@rest_controller
@request_mapping("/api/v1/links")
class OriginalLinks:
    calls = 0

    @post_mapping("")
    async def link(self, request: Request, body: Valid[Body[Link]]) -> dict:
        OriginalLinks.calls += 1
        context = tenant_context_from_request(request)
        return {
            "actor": context.actor,
            "bound_actor": current_tenant_context().actor,
            "source_id": body.source_id,
            "target_id": body.target_id,
        }


@pytest.mark.parametrize("client", [OriginalLinks], indirect=True)
def test_body_references_verified_before_original_and_canonical_actor_is_bound(client):
    context = client.native_app.state.context
    catalog = context.get_bean(CatalogService)

    async def seed():
        other = await catalog.create(f"{ISSUER}|outsider", "south", kind="workspace", name="Private")
        return other.id

    victim = client.portal.call(seed)
    policies = context.get_bean(LegacyOperationPolicies)

    async def verify(request, identity, tenant, workspace_id, parameters):
        body = await request.json()
        for identifier in (body["source_id"], body["target_id"]):
            entry = await catalog.get(identity.subject, tenant, identifier)
            if entry.workspace_id != workspace_id:
                raise AccessDenied("Resource is outside the selected workspace", code="ACCESS_DENIED")

    policies.register("canon", "POST", "/links", verify, permission="catalog:write")
    headers = {
        **bearer(),
        "X-Tenant-Id": "north",
        "X-Workspace-Id": client.workspace_id,
        "X-Actor": "forged-actor",
        "X-Agent-Token": "must-not-select-actor",
    }
    OriginalLinks.calls = 0
    denied = client.post(
        "/api/v1/canon/links", headers=headers, json={"source_id": client.workspace_id, "target_id": victim}
    )
    assert denied.status_code == 403
    assert OriginalLinks.calls == 0
    accepted = client.post(
        "/api/v1/canon/links",
        headers=headers,
        json={"source_id": client.workspace_id, "target_id": client.workspace_id},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["actor"] == accepted.json()["bound_actor"] == f"{ISSUER}|admin"
    assert OriginalLinks.calls == 1
    assert OriginalLinks.link.__globals__["tenant_context_from_request"] is tenant_context_from_request
    assert client.portal.call(current_tenant_context) is None
