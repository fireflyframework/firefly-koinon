# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "audit_native_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client, bearer = native.client, native.bearer


def test_native_audit_filters_pages_actors_and_tenant_permissions(client):
    assert (
        client.patch("/api/v1/profile", headers=bearer(), json={"display_name": "Audit reviewer"}).status_code
        == 200
    )
    for index in range(3):
        assert (
            client.post(
                "/api/v1/tenants/north/catalog",
                headers=bearer(),
                json={"kind": "workspace", "name": f"Audit source {index}"},
            ).status_code
            == 201
        )
    path = "/api/v1/tenants/north/audit"
    response = client.get(
        path,
        headers=bearer(),
        params={"q": "Audit source", "action": "catalog.created", "page": 2, "page_size": 1},
    )
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == 3 and page["page"] == 2 and page["pages"] == 3 and len(page["items"]) == 1
    assert page["actors"][native.ISSUER + "|admin"]["display_name"] == "Audit reviewer"
    assert "locale" not in page["actors"][native.ISSUER + "|admin"]
    response = client.get(
        path,
        headers=bearer(),
        params={"from_date": "2026-03-08", "through_date": "2026-03-08", "time_zone": "America/Los_Angeles"},
    )
    assert response.status_code == 200, response.text
    assert client.get(path, headers=bearer("viewer")).status_code == 403
    assert client.get("/api/v1/tenants/south/audit", headers=bearer()).status_code == 403
    assert client.get(path, headers=bearer(), params={"page_size": 101}).status_code == 400
    assert client.get(path, headers=bearer(), params={"from_date": "not-a-date"}).status_code in (400, 422)
