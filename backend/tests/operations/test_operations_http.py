# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator observations use native verified identity and current membership."""

import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "operations_native_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client


def test_signed_configuration_observations_require_operator_authority(client):
    path = "/api/v1/tenants/north/configuration"
    assert client.get(path).status_code == 401
    for subject in ("viewer", "editor", "analyst", "outsider"):
        assert client.get(path, headers=native.bearer(subject)).status_code == 403
    response = client.get(path, headers=native.bearer())
    assert response.status_code == 200, response.text
    deployment = response.json()["deployment"]
    assert deployment["ownership"] == "deployment" and deployment["read_only"] is True
    assert deployment["datasources"][0]["available"] is True
    assert deployment["metrics"]["available"] is None
    assert {item["id"]: item["available"] for item in deployment["storage"]} == {
        "documents": True,
        "structured": True,
    }
    assert "sqlite+" not in response.text and "app.db" not in response.text
    assert client.post(path + "/deployment", headers=native.bearer(), json={}).status_code == 404
