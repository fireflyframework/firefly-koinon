# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "export_policy_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client


def test_scoped_personal_token_can_request_explicit_export_share_rights_without_management(client):
    scopes = ["exports:read", "exports:write", "shares:read", "shares:write", "evidence:read"]
    issued = client.post(
        "/api/v1/tokens",
        headers=native.bearer("viewer"),
        json={
            "name": "Scoped knowledge sharing",
            "tenant_id": "north",
            "scopes": scopes,
            "workspace_ids": [client.workspace_id],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert issued.status_code == 201, issued.text
    actual = set(issued.json()["scopes"])
    assert set(scopes) <= actual and {"catalog:read", "chat:use"} <= actual
    assert "members:write" not in actual and "providers:write" not in actual
    headers = {"Authorization": "Bearer " + issued.json()["token"]}
    other = client.post(
        "/api/v1/tenants/north/catalog",
        headers=native.bearer(),
        json={"kind": "workspace", "name": "Foreign sharing scope"},
    ).json()
    assert client.get("/api/v1/tenants/north/catalog/" + other["id"], headers=headers).status_code == 403
    descriptors = client.get(
        "/api/v1/tokens/scopes",
        headers=native.bearer("viewer"),
        params={"tenant_id": "north", "workspace_id": client.workspace_id},
    ).json()["items"]
    assert {row["id"] for row in descriptors} >= set(scopes)
    assert all(row["name"] != row["id"] for row in descriptors if row["id"] in scopes)
