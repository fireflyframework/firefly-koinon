# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import bearer


def test_native_folder_move_checks_authentication_current_state_and_hierarchy(client):
    def create(kind, name, parent_id):
        response = client.post(
            "/api/v1/tenants/north/catalog",
            headers=bearer("editor"),
            json={"kind": kind, "name": name, "parent_id": parent_id},
        )
        assert response.status_code == 201, response.text
        return response.json()

    project = create("project", "Team", client.workspace_id)
    folder = create("collection", "Folder", project["id"])
    nested = create("collection", "Nested", folder["id"])
    url = f"/api/v1/tenants/north/catalog/{nested['id']}/move"
    decision = {
        "parent_id": project["id"],
        "expected_parent_id": folder["id"],
        "expected_updated_at": nested["updated_at"],
    }
    assert client.post(url, json=decision).status_code == 403
    assert client.post(url, json=decision, headers=bearer("viewer")).status_code == 403
    assert client.post(url, json=decision, headers=bearer("outsider")).status_code == 403
    assert client.post(url, json={"parent_id": project["id"]}, headers=bearer("editor")).status_code == 422
    moved = client.post(url, json=decision, headers=bearer("editor"))
    assert moved.status_code == 200, moved.text
    assert moved.json()["parent_id"] == project["id"]
    assert moved.json()["workspace_id"] == client.workspace_id
    stale = client.post(url, json=decision, headers=bearer("editor"))
    assert stale.status_code == 409, stale.text
    assert stale.json()["code"] == "CATALOG_CHANGED"


def test_system_spaces_are_protected_through_native_http_not_only_the_interface(client):
    async def provision_fixture():
        from koinon.catalog.service import CatalogService

        service = client.native_app.state.context.get_bean(CatalogService)
        return (
            await service._write_create(
                "system:installation",
                "north",
                kind="workspace",
                name="Organization",
                system_key="organization",
                installation_run_id="fixture-run",
            )
        ).id

    identifier = client.portal.call(provision_fixture)
    url = "/api/v1/tenants/north/catalog/" + identifier
    observed = client.get(url, headers=bearer())
    assert observed.status_code == 200
    assert observed.json()["system_managed"] is True
    for response in (client.delete(url, headers=bearer()), client.post(url + "/archive", headers=bearer())):
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "SYSTEM_SPACE_PROTECTED"
    assert client.patch(url, json={"system_key": None}, headers=bearer()).status_code == 422
    assert client.get(url, headers=bearer()).json()["created_by"] == "system:installation"
