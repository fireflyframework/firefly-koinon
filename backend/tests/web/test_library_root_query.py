# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import bearer


def test_existing_kind_predicate_pages_only_spaces_while_unfiltered_catalog_remains_recursive(client):
    base = "/api/v1/tenants/north/catalog"
    project = client.post(
        base, headers=bearer(), json={"kind": "project", "name": "General", "parent_id": client.workspace_id}
    )
    assert project.status_code == 201, project.text
    folder = client.post(
        base,
        headers=bearer(),
        json={"kind": "collection", "name": "Documents", "parent_id": project.json()["id"]},
    )
    assert folder.status_code == 201, folder.text
    home = client.get(base, headers=bearer(), params={"view": "library", "kind": "workspace", "page_size": 1})
    assert home.status_code == 200, home.text
    assert len(home.json()["items"]) == 1
    assert all(row["kind"] == "workspace" for row in home.json()["items"])
    assert home.json()["total"] >= 1
    raw = client.get(base, headers=bearer(), params={"view": "library", "page_size": 100})
    assert raw.status_code == 200, raw.text
    assert {client.workspace_id, project.json()["id"], folder.json()["id"]} <= {
        row["id"] for row in raw.json()["items"]
    }
    children = client.get(
        base, headers=bearer(), params={"view": "library", "parent_id": client.workspace_id}
    )
    assert children.status_code == 200, children.text
    assert [row["id"] for row in children.json()["items"]] == [project.json()["id"]]
