# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import base64

import pytest
from test_identity_provider_http import native


@pytest.fixture
def configured_identity_client(tmp_path, monkeypatch, request):
    import koinon.app

    original = koinon.app.create_application

    def configured(config):
        config["koinon"]["identity"] = {"master_key": base64.b64encode(bytes(range(32))).decode()}
        return original(config)

    monkeypatch.setattr(koinon.app, "create_application", configured)
    yield from native.client.__wrapped__(tmp_path, monkeypatch, request)


def test_configured_key_is_bound_before_native_security_materializes_public_hooks(configured_identity_client):
    client = configured_identity_client
    response = client.post(
        "/api/v1/tenants/north/identity/providers",
        headers=native.bearer(),
        json={
            "kind": "keycloak",
            "name": "Configured native credentials",
            "settings": {"kind": "keycloak", "issuer": native.ISSUER, "client_id": "browser"},
            "credential": {"kind": "keycloak", "secret": "synthetic-private-credential"},
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["credential_configured"] is True
    assert "synthetic-private-credential" not in response.text
