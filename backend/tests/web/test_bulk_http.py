# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import socket
from hashlib import sha256

import pytest
from conftest import ISSUER, bearer

from koinon.catalog.service import CatalogService
from koinon.knowledge.bulk.settings import BulkSettings


@pytest.fixture(autouse=True)
def native_bulk_slice(monkeypatch):
    from pyfly.container.scanner import scan_package

    import koinon.app
    from koinon.knowledge.bulk.controllers import FileBatchController
    from koinon.web.projection import register_controller

    original = koinon.app.create_application

    def composed(config):
        app = original(config)
        scan_package("koinon.knowledge.bulk", app.state.context.container)
        register_controller(app.state.context, FileBatchController)
        return app

    def denied(*args, **kwargs):
        raise AssertionError("No external sockets in the native bulk HTTP slice")

    monkeypatch.setattr(koinon.app, "create_application", composed)
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def test_native_bulk_routes_validate_stream_hash_scope_and_private_pagination(client, tmp_path):
    root = tmp_path / "bulk-private"
    root.mkdir(mode=0o700)
    context = client.native_app.state.context
    context.get_bean(BulkSettings).storage_root = str(root)

    async def target():
        catalog = context.get_bean(CatalogService)
        project = await catalog.create(
            ISSUER + "|editor", "north", kind="project", name="Project", parent_id=client.workspace_id
        )
        parent = await catalog.create(
            ISSUER + "|editor", "north", kind="collection", name="Collection", parent_id=project.id
        )
        return {"workspace_id": client.workspace_id, "project_id": project.id, "parent_id": parent.id}

    destination = client.portal.call(target)
    capability = client.get(
        "/api/v1/tenants/north/source-batch-capabilities",
        params={"workspace_id": client.workspace_id},
        headers=bearer("editor"),
    )
    assert capability.status_code == 200, capability.text
    assert (
        capability.json()["modes"] == ["document", "dataset"]
        and capability.json()["automatic_unknown_replay"] is False
    )
    assert capability.json()["configured"] is True and str(root) not in capability.text
    path = "/api/v1/tenants/north/sources/batches"
    body = {
        "destination": destination,
        "items": [
            {
                "client_item_id": "one",
                "filename": "facts.md",
                "mode": "document",
                "size_bytes": 8,
                "sha256": sha256(b"original").hexdigest(),
            }
        ],
    }
    headers = {**bearer("editor"), "Idempotency-Key": "native-create"}
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 201, response.text
    batch = response.json()
    assert response.headers["cache-control"] == "private, no-store"
    page = client.get(path, headers=bearer("editor")).json()
    assert page["total"] == 1 and page["items"][0]["id"] == batch["id"]
    assert client.get(path, headers=bearer("viewer")).json()["total"] == 0
    assert client.get(path + "/" + batch["id"], headers=bearer("viewer")).status_code == 403
    assert client.get(path + "?page_size=101", headers=bearer("editor")).status_code in [400, 422]
    items = client.get(path + "/" + batch["id"] + "/items", headers=bearer("editor")).json()
    item = items["items"][0]
    raw = path + "/" + batch["id"] + "/items/" + item["id"] + "/content"
    uploaded = client.put(
        raw, headers={**bearer("editor"), "Idempotency-Key": "native-upload"}, content=b"original"
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["sha256"] == body["items"][0]["sha256"]
    assert "object_key" not in uploaded.text and str(root) not in uploaded.text
    assert (
        client.put(
            raw, headers={**bearer("editor"), "Idempotency-Key": "native-upload"}, content=b"changed!"
        ).status_code
        == 409
    )
    dataset = {**body, "items": [{**body["items"][0], "mode": "dataset"}]}
    assert (
        client.post(path, headers={**headers, "Idempotency-Key": "dataset"}, json=dataset).status_code == 201
    )
