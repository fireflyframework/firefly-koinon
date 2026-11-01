# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from datetime import datetime

import pytest
from conftest import ISSUER, bearer

from koinon.catalog.service import CatalogService


def folder(client):
    project = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer("editor"),
        json={"kind": "project", "name": "Project", "parent_id": client.workspace_id},
    ).json()
    response = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer("editor"),
        json={"kind": "collection", "name": "Folder", "parent_id": project["id"]},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_patch_timestamp_precondition_is_optional_but_stale_changes_cannot_overwrite(client):
    initial = folder(client)
    url = "/api/v1/tenants/north/catalog/" + initial["id"]
    fresh = client.patch(
        url, headers=bearer("editor"), json={"name": "First", "expected_updated_at": initial["updated_at"]}
    )
    assert fresh.status_code == 200, fresh.text
    stale = client.patch(
        url,
        headers=bearer("editor"),
        json={"name": "Overwritten", "expected_updated_at": initial["updated_at"]},
    )
    assert stale.status_code == 409 and stale.json()["code"] == "CATALOG_CHANGED", stale.text
    assert client.get(url, headers=bearer()).json()["name"] == "First"
    assert client.patch(url, headers=bearer("editor"), json={"name": "Legacy"}).status_code == 200


@pytest.mark.parametrize("action", ["archive", "restore"])
def test_lifecycle_exact_query_precondition_does_not_break_bodyless_clients(client, action):
    initial = folder(client)
    url = "/api/v1/tenants/north/catalog/" + initial["id"]
    client.patch(url, headers=bearer("editor"), json={"name": "Changed"})
    if action == "restore":
        assert client.post(url + "/archive", headers=bearer("editor")).status_code == 200
    stale = client.post(
        url + "/" + action, headers=bearer("editor"), params={"expected_updated_at": initial["updated_at"]}
    )
    assert stale.status_code == 409 and stale.json()["code"] == "CATALOG_CHANGED", stale.text
    now = client.get(url, headers=bearer()).json()
    assert (
        client.post(
            url + "/" + action, headers=bearer("editor"), params={"expected_updated_at": now["updated_at"]}
        ).status_code
        == 200
    )
    if action == "archive":
        assert client.post(url + "/restore", headers=bearer("editor")).status_code == 200
        assert client.post(url + "/archive", headers=bearer("editor")).status_code == 200
    else:
        assert client.post(url + "/archive", headers=bearer("editor")).status_code == 200
        assert client.post(url + "/restore", headers=bearer("editor")).status_code == 200


def test_naive_or_invalid_preconditions_never_mutate_and_authority_remains_required(client):
    initial = folder(client)
    url = "/api/v1/tenants/north/catalog/" + initial["id"]
    for timestamp in ("2026-11-01T00:00:00", "not-a-timestamp"):
        response = client.post(
            url + "/archive", headers=bearer("editor"), params={"expected_updated_at": timestamp}
        )
        assert response.status_code == 422, response.text
    denied = client.patch(
        url, headers=bearer("viewer"), json={"name": "No", "expected_updated_at": initial["updated_at"]}
    )
    assert denied.status_code == 403
    assert client.get(url, headers=bearer()).json()["status"] != "archived"


def test_two_native_writers_with_the_same_expected_timestamp_cannot_both_commit(client):
    initial = folder(client)
    expected = datetime.fromisoformat(initial["updated_at"].replace("Z", "+00:00"))

    async def race():
        service = client.native_app.state.context.get_bean(CatalogService)
        return await asyncio.gather(
            *(
                service.update(
                    ISSUER + "|editor", "north", initial["id"], {"name": name}, expected_updated_at=expected
                )
                for name in ("One", "Two")
            ),
            return_exceptions=True,
        )

    results = client.portal.call(race)
    assert sum(not isinstance(value, BaseException) for value in results) == 1, repr(results)
    assert [value.code for value in results if isinstance(value, BaseException)] == ["CATALOG_CHANGED"]
