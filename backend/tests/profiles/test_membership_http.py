# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "members_native_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client, bearer = native.client, native.bearer


def test_named_membership_pages_are_authorized_filtered_and_counted(client):
    response = client.patch(
        "/api/v1/profile", headers=bearer("viewer"), json={"display_name": "Directory researcher"}
    )
    assert response.status_code == 200
    response = client.get(
        "/api/v1/tenants/north/members?q=researcher&page_size=1&role=viewer", headers=bearer()
    )
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 1 and page["pages"] == 1 and page["page_size"] == 1
    assert page["items"][0]["subject"] == native.ISSUER + "|viewer"
    assert page["actors"][native.ISSUER + "|viewer"]["display_name"] == "Directory researcher"
    assert "locale" not in page["actors"][native.ISSUER + "|viewer"]
    assert client.get("/api/v1/tenants/north/members", headers=bearer("viewer")).status_code == 403
    assert client.get("/api/v1/tenants/north/members?page_size=101", headers=bearer()).status_code == 400
    assert (
        client.patch(
            "/api/v1/tenants/north/members/admin", headers=bearer(), json={"role": "viewer"}
        ).status_code
        == 409
    )
