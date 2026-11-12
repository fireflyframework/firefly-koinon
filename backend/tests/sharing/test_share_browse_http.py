# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "share_http_fixture", Path(__file__).parents[1] / "exports/test_export_share_http.py"
)
assert spec and spec.loader
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)
client = fixtures.client


def test_native_share_browse_retains_private_unknown_total_and_validates_selection(client):
    headers, selection = fixtures.selected_message(client)
    base = "/api/v1/tenants/north/shares"
    preview = client.post(base + "/reviews", headers=headers, json=selection)
    assert preview.status_code == 201, preview.text
    created = client.post(
        base,
        headers=headers,
        json={"review_id": preview.json()["id"], "expected_revision": preview.json()["revision"]},
    )
    assert created.status_code == 201, created.text
    response = client.post(base + "/browse", headers=headers, json={"reader_source_connections": []})
    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["items"]] == [created.json()["id"]]
    assert response.json()["total"] is None and response.json()["total_is_exact"] is False
    assert response.json()["next_cursor"] is None
    assert "no-store" in response.headers["cache-control"]
    assert client.post(base + "/browse", headers=headers, json={"page_size": 101}).status_code == 422
    assert client.post(base + "/browse", json={}).status_code == 403
