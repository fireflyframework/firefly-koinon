# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "scoped_context_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client, bearer = native.client, native.bearer


def test_context_distinguishes_workspace_admin_and_personal_token_authority(client):
    workspace = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer(),
        json={"kind": "workspace", "name": "Scoped administration"},
    ).json()
    grant = client.post(
        "/api/v1/tenants/north/members",
        headers=bearer(),
        json={"subject": native.ISSUER + "|scoped-admin", "role": "admin", "workspace_id": workspace["id"]},
    )
    assert grant.status_code == 201, grant.text
    response = client.get("/api/v1/context", headers=bearer("scoped-admin"))
    assert response.status_code == 200, response.text
    context = response.json()
    assert context["tenants"][0]["permissions"] == []
    assert "members:write" in context["workspace_permissions"][workspace["id"]]
    assert (
        client.get("/api/v1/tenants/north/configuration", headers=bearer("scoped-admin")).status_code == 403
    )
    token = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Read own workspace",
            "tenant_id": "north",
            "scopes": ["catalog:read"],
            "workspace_ids": [workspace["id"]],
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert token.status_code == 201, token.text
    restricted = client.get(
        "/api/v1/context", headers={"Authorization": "Bearer " + token.json()["token"]}
    ).json()
    assert set(restricted["workspace_permissions"]) == {workspace["id"]}
    assert restricted["workspace_permissions"][workspace["id"]] == ["catalog:read"]
