# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import bearer


def test_catalog_metadata_preserves_unsafe_integers_without_changing_flags(client):
    response = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer(),
        json={
            "kind": "project",
            "name": "Exact metadata",
            "parent_id": client.workspace_id,
            "metadata": {
                "large_id": 9007199254740993,
                "nested": [{"negative": -9007199254740993, "enabled": True}],
                "boundary": 9007199254740991,
            },
        },
    )
    assert response.status_code == 201, response.text
    expected = {
        "large_id": "9007199254740993",
        "nested": [{"negative": "-9007199254740993", "enabled": True}],
        "boundary": 9007199254740991,
    }
    assert response.json()["metadata"] == expected
    read = client.get(
        "/api/v1/tenants/north/catalog/" + response.json()["id"], headers=bearer("viewer")
    )
    assert read.json()["metadata"] == expected


def test_portable_json_keeps_exact_decimal_text_and_safe_boundaries():
    from decimal import Decimal

    from koinon.api.json_values import portable_json

    assert portable_json(
        {
            "amount": Decimal("12345678901234567890.00100"),
            "values": [False, None, -9007199254740991, 9007199254740992, -9007199254740992],
        }
    ) == {
        "amount": "12345678901234567890.00100",
        "values": [False, None, -9007199254740991, "9007199254740992", "-9007199254740992"],
    }
