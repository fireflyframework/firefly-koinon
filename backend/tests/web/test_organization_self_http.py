# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import bearer


def test_self_profile_uses_own_identity_without_directory_access(client):
    response = client.get(
        "/api/v1/tenants/north/organization/people/me", headers=bearer("viewer")
    )
    assert response.status_code == 200
    assert response.json()["source"] == "unassigned"
    denied = client.get(
        "/api/v1/tenants/north/organization/people/another-person", headers=bearer("viewer")
    )
    assert denied.status_code == 403
