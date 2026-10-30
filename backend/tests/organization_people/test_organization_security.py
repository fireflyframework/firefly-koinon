# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from koinon.catalog.errors import AccessDenied
from koinon.organization_people.controllers import browser
from koinon.organization_people.dtos import (
    OrganizationPerson,
    OrganizationPersonPage,
    OrganizationPersonPatch,
)
from koinon.organization_people.security import organization_identity
from koinon.security.identity import RequestIdentity


def test_directory_request_boundary_rejects_malformed_or_out_of_scope_tokens(monkeypatch):
    monkeypatch.setattr(
        "koinon.organization_people.security.identity_from_request",
        lambda _: RequestIdentity("https://issuer|member", True, "bearer"),
    )
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/bff/api/v1/tenants/north/organization/people",
            "headers": [],
        }
    )
    for token in (
        None,
        {},
        {"tenant_id": "south", "scopes": ["members:write"]},
        {"tenant_id": "north", "scopes": ["catalog:read"], "asset_ids": ["asset"]},
        {"tenant_id": "north", "scopes": ["catalog:read"], "workspace_ids": ["private"]},
        {"tenant_id": "north", "scopes": "members:write"},
    ):
        request.state.security_context = SimpleNamespace(attributes={"koinon_token": token})
        with pytest.raises(AccessDenied):
            organization_identity(request, "north", "shared")
    request.state.security_context = SimpleNamespace(
        attributes={
            "koinon_token": {"tenant_id": "north", "scopes": ["catalog:read"], "workspace_ids": ["shared"]}
        }
    )
    assert organization_identity(request, "north", "shared").subject == "https://issuer|member"
    with pytest.raises(AccessDenied):
        organization_identity(request, "north", "shared", write=True)


def test_source_change_requires_one_explicit_nonnull_choice():
    for values in (
        {"managed_provider_id": None},
        {"managed_provider_id": ""},
        {"managed_provider_id": "  "},
        {"managed_provider_id": "provider", "manage_locally": True},
        {"external_subject": "browser-claim"},
    ):
        with pytest.raises(ValidationError):
            OrganizationPersonPatch(expected_revision=1, **values)
    assert OrganizationPersonPatch(expected_revision=1).managed_provider_id is None


def test_bff_projection_rewrites_only_authorized_avatar_paths():
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/bff/api/v1/tenants/north/organization/people",
            "headers": [],
        }
    )
    output = OrganizationPersonPage(
        items=[
            OrganizationPerson(
                display_name="Member", avatar_url="/api/v1/tenants/north/organization/people/id/avatar"
            )
        ],
        total=1,
        page=1,
        page_size=25,
        pages=1,
    )
    assert browser(output, request).items[0].avatar_url.startswith("/bff/api/v1/")
    assert "subject" not in browser(output, request).items[0].model_dump()
