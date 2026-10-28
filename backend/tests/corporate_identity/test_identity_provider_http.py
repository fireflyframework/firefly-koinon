# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "identity_native_http_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
bearer = native.bearer


client = native.client


def test_native_signed_http_provider_test_scope_and_write_only_credentials(client):
    root = "/api/v1/tenants/north/identity/providers"
    body = {
        "kind": "keycloak",
        "name": "Corporate research",
        "settings": {"kind": "keycloak", "issuer": native.ISSUER, "client_id": "browser"},
    }
    assert client.get(root, headers=bearer("viewer")).status_code == 403
    created = client.post(root, headers=bearer(), json=body)
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["status"] == "draft" and row["canonical_issuer"] == native.ISSUER
    assert "credential" not in row and row["credential_configured"] is False
    assert client.get(root + "?q=research&page_size=1", headers=bearer()).json()["total"] == 1
    assert (
        client.get(root.replace("/north/", "/south/") + "/" + row["id"], headers=bearer()).status_code == 403
    )
    proof = client.post(root + "/" + row["id"] + "/test", headers=bearer(), json={"expected_revision": 1})
    assert proof.status_code == 201, proof.text
    assert proof.json()["authorization_url"].startswith("/oauth2/authorization/koinon?identity_test=")
    assert (
        client.get(root + "/" + row["id"] + "/tests/" + proof.json()["id"], headers=bearer()).json()["status"]
        == "pending"
    )
    blocked = client.post(
        root + "/" + row["id"] + "/activate",
        headers=bearer(),
        json={"expected_revision": 1, "validation_id": proof.json()["id"]},
    )
    assert blocked.status_code == 409
    secret = "controlled-secret-must-not-be-returned"
    missing_key = client.patch(
        root + "/" + row["id"],
        headers=bearer(),
        json={"expected_revision": 1, "credential": {"kind": "keycloak", "secret": secret}},
    )
    assert missing_key.status_code == 503 and secret not in missing_key.text
    assert client.get(root + "/" + row["id"] + "/groups", headers=bearer()).status_code == 503
    disabled = client.post(
        root + "/" + row["id"] + "/disable", headers=bearer(), json={"expected_revision": 1}
    )
    assert disabled.status_code == 200 and disabled.json()["status"] == "disabled"
