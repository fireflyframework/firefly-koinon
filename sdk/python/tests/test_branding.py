# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx

from koinon_sdk import (
    BrandingResetInput,
    BrandingValues,
    KoinonClient,
    OrganizationBrandingInput,
)


async def test_branding_routes_revision_and_explicit_asset_clear_are_typed():
    calls = []
    values = BrandingValues(product_name="Example", logo_light=None)

    def handle(request):
        calls.append(request)
        if request.url.path == "/api/v1/branding/defaults":
            return httpx.Response(200, json=values.model_dump(mode="json"))
        return httpx.Response(
            200,
            json={
                "tenant_id": "north/one",
                "revision": 2,
                "origin": "organization",
                "branding": values.model_dump(mode="json"),
            },
        )

    async with KoinonClient(
        "https://knowledge.example/api/v1",
        token_provider=lambda: "fixture",
        transport=httpx.MockTransport(handle),
    ) as client:
        assert (await client.branding_defaults()).product_name == "Example"
        assert (await client.organization_branding("north/one")).revision == 2
        await client.update_organization_branding(
            "north/one", OrganizationBrandingInput(expected_revision=1, branding=values)
        )
        await client.reset_organization_branding("north/one", BrandingResetInput(expected_revision=2))
    assert [(request.method, request.url.raw_path) for request in calls] == [
        ("GET", b"/api/v1/branding/defaults"),
        ("GET", b"/api/v1/tenants/north%2Fone/branding"),
        ("PUT", b"/api/v1/tenants/north%2Fone/branding"),
        ("POST", b"/api/v1/tenants/north%2Fone/branding/reset"),
    ]
    payload = json.loads(calls[2].content)
    assert payload["expected_revision"] == 1
    assert "logo_light" in payload["branding"] and payload["branding"]["logo_light"] is None
    assert json.loads(calls[3].content) == {"expected_revision": 2}
