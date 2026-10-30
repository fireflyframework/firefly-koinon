# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from conftest import bearer

from koinon.organization_branding.dtos import BrandingValues


def body(revision=0):
    return {
        "expected_revision": revision,
        "branding": BrandingValues(product_name="Organization").model_dump(),
    }


def test_deployment_defaults_are_public_but_organization_branding_requires_membership(client):
    defaults = client.get("/api/v1/branding/defaults")
    assert defaults.status_code == 200, defaults.text
    assert defaults.json()["product_name"] == "koinon"
    assert "tenant_id" not in defaults.json()
    assert client.put("/api/v1/branding/defaults", json=body()).status_code in (401, 403)
    path = "/api/v1/tenants/north/branding"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=bearer("outsider")).status_code == 403
    baseline = client.get(path, headers=bearer("viewer"))
    assert baseline.status_code == 200, baseline.text
    assert (baseline.json()["origin"], baseline.json()["revision"]) == ("deployment", 0)
    for subject in ("viewer", "editor", "analyst", "outsider"):
        assert client.put(path, headers=bearer(subject), json=body()).status_code == 403
        assert (
            client.post(path + "/reset", headers=bearer(subject), json={"expected_revision": 0}).status_code
            == 403
        )
    saved = client.put(path, headers=bearer(), json=body())
    assert saved.status_code == 200, saved.text
    assert saved.json()["revision"] == 1 and saved.json()["branding"]["product_name"] == "Organization"
    assert client.put(path, headers=bearer(), json=body()).status_code == 409
    reset = client.post(path + "/reset", headers=bearer(), json={"expected_revision": 1})
    assert reset.status_code == 200, reset.text
    assert (reset.json()["origin"], reset.json()["revision"]) == ("deployment", 2)
    assert client.post(path + "/reset", headers=bearer(), json={"expected_revision": 1}).status_code == 409


@pytest.mark.parametrize(
    "change",
    [
        {"expected_revision": True},
        {"extra": "unexpected"},
        {"branding": {"product_name": "bad\nname"}},
        {"branding": {"logo_light": "https://example.invalid/logo.png"}},
    ],
)
def test_branding_http_rejects_invalid_requests_without_revision_changes(client, change):
    path = "/api/v1/tenants/north/branding"
    invalid = client.put(path, headers=bearer(), json=body() | change)
    assert invalid.status_code in (400, 422), invalid.text
    assert client.get(path, headers=bearer()).json()["revision"] == 0


@pytest.mark.parametrize("scope", [
    "catalog:read", "knowledge:search", "chat:use", "query:execute", "exports:write", "shares:write",
])
def test_workspace_tokens_read_only_existing_scope_branding_and_cannot_mutate(client, scope):
    issued = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Controlled branding read",
            "tenant_id": "north",
            "scopes": [scope],
            "workspace_ids": [client.workspace_id],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert issued.status_code == 201, issued.text
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    path = "/api/v1/tenants/north/branding"
    result = client.get(path, headers=headers)
    assert result.status_code == 200, result.text
    assert client.get("/api/v1/tenants/south/branding", headers=headers).status_code == 403
    assert client.put(path, headers=headers, json=body()).status_code == 403
    assert client.post(path + "/reset", headers=headers, json={"expected_revision": 0}).status_code == 403


def test_browser_sign_in_can_read_deployment_identity_without_a_session(client):
    response = client.get("/bff/api/v1/branding/defaults")
    assert response.status_code == 200, response.text
    assert response.json() == client.get("/api/v1/branding/defaults").json()
    assert client.get("/bff/api/v1/tenants/north/branding").status_code == 401
    for method in ("POST", "PUT", "DELETE"):
        assert client.request(method, "/bff/api/v1/branding/defaults", json={}).status_code in (401, 403)


def test_invalid_raster_is_rejected_with_field_error_without_changing_revision(client):
    path = "/api/v1/tenants/north/branding"
    invalid = body()
    invalid["branding"]["logo_light"] = "data:image/png;base64,AA=="
    response = client.put(path, headers=bearer(), json=invalid)
    assert response.status_code == 422, response.text
    assert "branding" in response.text and "logo_light" in response.text
    assert "data:image" not in response.text
    assert client.get(path, headers=bearer()).json()["revision"] == 0


def test_borderline_link_contrast_is_rejected_with_palette_location_without_revision_change(client):
    path = "/api/v1/tenants/north/branding"
    invalid = body()
    invalid["branding"]["palette"]["light"]["accent"] = "#777777"
    response = client.put(path, headers=bearer(), json=invalid)
    assert response.status_code == 422, response.text
    assert "branding.palette.light" in response.text and "accent" in response.text
    assert client.get(path, headers=bearer()).json()["revision"] == 0


def test_actual_http_write_sanitizes_images_off_the_request_event_loop(client, monkeypatch):
    import asyncio
    import base64
    from io import BytesIO

    from PIL import Image

    from koinon.organization_branding import dtos

    output = BytesIO()
    Image.new("RGB", (16, 16), "white").save(output, format="PNG")
    request = body()
    request["branding"]["logo_light"] = "data:image/png;base64," + base64.b64encode(
        output.getvalue()
    ).decode()
    original, observed = dtos.sanitize_image, []

    def checked(value):
        if value is not None:
            try:
                asyncio.get_running_loop()
                observed.append("event_loop")
            except RuntimeError:
                observed.append("worker")
        return original(value)

    monkeypatch.setattr(dtos, "sanitize_image", checked)
    response = client.put("/api/v1/tenants/north/branding", headers=bearer(), json=request)
    assert response.status_code == 200, response.text
    assert observed and set(observed) == {"worker"}
    assert response.json()["branding"]["logo_light"].startswith("data:image/png;base64,")


@pytest.mark.parametrize("scope", ["exports:write", "shares:write"])
def test_presentation_reads_preserve_write_token_asset_ancestry(client, scope):
    from conftest import ISSUER

    from koinon.catalog.repositories import CatalogRepository
    from koinon.catalog.service import CatalogService

    async def asset():
        catalog = client.native_app.state.context.get_bean(CatalogService)
        parent = client.workspace_id
        for kind in ("project", "collection", "source", "document"):
            entry = await catalog.create(f"{ISSUER}|admin", "north", kind=kind, name=kind, parent_id=parent)
            parent = entry.id
        return entry.id

    identifier = client.portal.call(asset)
    issued = client.post("/api/v1/tokens", headers=bearer(), json={
        "name": "Asset-bound presentation", "tenant_id": "north", "scopes": [scope],
        "workspace_ids": [client.workspace_id], "asset_ids": [identifier],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    })
    assert issued.status_code == 201, issued.text
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    assert client.get("/api/v1/tenants/north/branding", headers=headers).status_code == 200
    assert client.get("/api/v1/tenants/south/branding", headers=headers).status_code == 403

    async def remove():
        repository = client.native_app.state.context.get_bean(CatalogRepository)
        await repository.delete_by_id(identifier)

    client.portal.call(remove)
    assert client.get("/api/v1/tenants/north/branding", headers=headers).status_code == 403
