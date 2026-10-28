# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exercise profiles through the real native signed-bearer/ASGI fixture."""

import importlib.util
from io import BytesIO
from pathlib import Path

from PIL import Image

spec = importlib.util.spec_from_file_location(
    "profiles_native_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client
bearer = native.bearer


def avatar_bytes():
    output = BytesIO()
    Image.new("RGB", (96, 96), "navy").save(output, format="PNG")
    return output.getvalue()


def test_signed_native_profile_http_and_personal_ownership(client):
    assert client.get("/api/v1/profile").status_code == 401
    response = client.patch(
        "/api/v1/profile",
        headers=bearer(),
        json={
            "display_name": "Native researcher",
            "locale": "es-MX",
            "time_zone": "America/Mexico_City",
            "response_language": "es",
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["subject"] == native.ISSUER + "|admin"
    assert client.get("/api/v1/profile", headers=bearer("viewer")).json()["display_name"] == ""
    denied = client.patch("/api/v1/profile", headers=bearer(), json={"subject": native.ISSUER + "|viewer"})
    assert denied.status_code in (400, 422)
    assert (
        client.patch("/api/v1/profile", headers=bearer(), json={"time_zone": "Invalid/Zone"}).status_code
        == 400
    )


def test_avatar_binary_contract_size_bounds_and_conditional_auth(client):
    headers = {**bearer(), "Content-Type": "image/png"}
    response = client.post("/api/v1/profile/avatar", headers=headers, content=avatar_bytes())
    assert response.status_code == 200, response.text
    picture = client.get(response.json()["avatar_url"], headers=bearer())
    assert picture.status_code == 200 and picture.headers["Content-Type"] == "image/jpeg"
    assert picture.headers["X-Content-Type-Options"] == "nosniff"
    with Image.open(BytesIO(picture.content)) as image:
        assert max(image.size) <= 128 and not image.getexif()
    conditional = client.get(
        "/api/v1/profile/avatar", headers={**bearer(), "If-None-Match": picture.headers["ETag"]}
    )
    assert conditional.status_code == 304
    assert client.get("/api/v1/profile/avatar", headers=bearer("viewer")).status_code == 404
    too_large = client.post("/api/v1/profile/avatar", headers=headers, content=b"x" * 2_097_153)
    assert too_large.status_code == 413
    assert client.post("/api/v1/profile/avatar", headers=headers, content=b"<svg/>").status_code == 400
    assert client.delete("/api/v1/profile/avatar", headers=bearer()).status_code == 200


def test_people_directory_is_admin_only_and_tenant_scoped(client):
    assert client.get("/api/v1/tenants/north/people", headers=bearer("viewer")).status_code == 403
    people = client.get("/api/v1/tenants/north/people", headers=bearer())
    assert people.status_code == 200, people.text
    assert len(people.json()["items"]) == 4
    assert all(row["subject"].startswith(native.ISSUER + "|") for row in people.json()["items"])
    assert all("locale" not in row for row in people.json()["items"])
    assert client.get("/api/v1/tenants/south/people", headers=bearer()).status_code == 403


def test_verified_native_name_and_locale_are_persisted_before_user_edits(client):
    import time

    import jwt

    token = jwt.encode(
        {
            "iss": native.ISSUER,
            "sub": "admin",
            "aud": "koinon-api",
            "exp": int(time.time()) + 300,
            "name": "Verified Administrator",
            "locale": "es-MX",
        },
        native.KEY,
        algorithm="RS256",
        headers={"kid": "local-key"},
    )
    profile = client.get("/api/v1/profile", headers={"Authorization": "Bearer " + token})
    assert profile.status_code == 200, profile.text
    assert profile.json()["display_name"] == "Verified Administrator" and profile.json()["locale"] == "es-MX"
    assert client.get("/api/v1/profile", headers=bearer()).json()["display_name"] == "Verified Administrator"


def test_directory_avatar_rechecks_membership_even_for_conditional_cache(client):
    uploaded = client.post(
        "/api/v1/profile/avatar",
        headers={**bearer("viewer"), "Content-Type": "image/png"},
        content=avatar_bytes(),
    )
    assert uploaded.status_code == 200, uploaded.text
    people = client.get("/api/v1/tenants/north/people", headers=bearer()).json()["items"]
    person = next(row for row in people if row["subject"] == native.ISSUER + "|viewer")
    assert person["profile_id"] and "|" not in person["profile_id"]
    avatar_path = "/api/v1/tenants/north/people/" + person["profile_id"] + "/avatar"
    image = client.get(avatar_path, headers=bearer())
    assert image.status_code == 200, image.text
    assert client.get(avatar_path, headers=bearer("viewer")).status_code == 403
    assert (
        client.get(
            "/api/v1/tenants/south/people/" + person["profile_id"] + "/avatar", headers=bearer()
        ).status_code
        == 403
    )
    removed = client.patch("/api/v1/tenants/north/members/viewer", headers=bearer(), json={"active": False})
    assert removed.status_code == 200, removed.text
    assert (
        client.get(avatar_path, headers={**bearer(), "If-None-Match": image.headers["ETag"]}).status_code
        == 403
    )


def test_personal_token_profile_permissions_are_separate_from_knowledge_scopes(client):
    from datetime import UTC, datetime, timedelta

    def issue(scopes):
        response = client.post(
            "/api/v1/tokens",
            headers=bearer(),
            json={
                "name": "Profile permission regression",
                "tenant_id": "north",
                "scopes": scopes,
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        assert response.status_code == 201, response.text
        return {"Authorization": "Bearer " + response.json()["token"]}

    knowledge = issue(["catalog:read"])
    assert client.get("/api/v1/profile", headers=knowledge).status_code == 403
    read = issue(["profile:read"])
    assert client.get("/api/v1/profile", headers=read).status_code == 200
    assert client.patch("/api/v1/profile", headers=read, json={"display_name": "Denied"}).status_code == 403
    write = issue(["profile:write"])
    changed = client.patch("/api/v1/profile", headers=write, json={"display_name": "Personal token owner"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["subject"] == native.ISSUER + "|admin"
    assert client.get("/api/v1/tokens", headers=write).status_code == 403
