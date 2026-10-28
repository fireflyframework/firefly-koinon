# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "invitation_native_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client, bearer = native.client, native.bearer


def test_signed_native_invitation_protocol_and_no_secret_replay(client):
    path = "/api/v1/tenants/north/invitations"
    assert client.post(path, headers=bearer("viewer"), json={"role": "editor"}).status_code == 403
    created = client.post(path, headers=bearer(), json={"role": "editor"})
    assert created.status_code == 201, created.text
    assert created.headers["cache-control"] == "no-store"
    token = created.json()["token"]
    listing = client.get(path, headers=bearer()).json()
    assert listing["total"] == 1 and "token" not in listing["items"][0] and token not in str(listing)
    assert client.post("/api/v1/invitations/inspect", json={"token": token}).status_code in (401, 403)
    preview = client.post("/api/v1/invitations/inspect", headers=bearer("new-person"), json={"token": token})
    assert preview.status_code == 200 and preview.json()["role"] == "editor", preview.text
    accepted = client.post("/api/v1/invitations/redeem", headers=bearer("new-person"), json={"token": token})
    assert accepted.status_code == 201, accepted.text
    assert accepted.json()["subject"] == native.ISSUER + "|new-person"
    assert (
        client.post(
            "/api/v1/invitations/redeem", headers=bearer("another"), json={"token": token}
        ).status_code
        == 403
    )
    assert client.get(path + "?status=accepted", headers=bearer()).json()["total"] == 1


def test_personal_tokens_cannot_manage_or_accept_invitations(client):
    from datetime import UTC, datetime, timedelta

    path = "/api/v1/tenants/north/invitations"
    created = client.post(path, headers=bearer(), json={"role": "viewer"}).json()
    token = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "Restricted API",
            "tenant_id": "north",
            "scopes": ["members:write"],
            "expires_at": (datetime.now(UTC) + timedelta(days=1)).isoformat(),
        },
    )
    assert token.status_code == 201, token.text
    headers = {"Authorization": "Bearer " + token.json()["token"]}
    assert client.post(path, headers=headers, json={"role": "viewer"}).status_code == 403
    for operation in ("inspect", "redeem"):
        assert (
            client.post(
                "/api/v1/invitations/" + operation, headers=headers, json={"token": created["token"]}
            ).status_code
            == 403
        )
    assert client.delete(path + "/" + created["invitation"]["id"], headers=bearer()).status_code == 204
    assert (
        client.post(
            "/api/v1/invitations/inspect", headers=bearer("new"), json={"token": created["token"]}
        ).status_code
        == 403
    )
