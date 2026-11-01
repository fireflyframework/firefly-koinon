# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest
from http_fixtures import ISSUER, bearer
from http_fixtures import client as client
from http_fixtures import oauth_client as oauth_client
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from test_mcp_http import call, create_pat
from test_mcp_scope_upgrade import oauth_token
from test_mcp_server import protocol, settings

from koinon.catalog.repositories import MembershipRepository
from koinon.mcp.server import create_mcp_server


def create(client, kind, parent, name="Folder"):
    response = client.post(
        "/api/v1/tenants/north/catalog",
        headers=bearer("editor"),
        json={"kind": kind, "name": name, "parent_id": parent},
    )
    assert response.status_code == 201, response.text
    return response.json()


def result(response):
    assert response.status_code == 200, response.text
    value = response.json()["result"]
    assert not value["isError"], value
    return value["structuredContent"]


def test_real_user_can_organize_catalog_without_apps_but_not_publish_content(client):
    project = create(client, "project", client.workspace_id, "Project")
    other = create(client, "collection", project["id"], "Destination")
    token = create_pat(client, "editor", ["catalog:read", "catalog:write"])["token"]
    initial = result(
        call(
            client,
            token,
            "koinon_create_folder",
            {"tenant_id": "north", "kind": "collection", "name": "New folder", "parent_id": project["id"]},
        )
    )
    assert initial["created_by"] == ISSUER + "|editor"
    updated = result(
        call(
            client,
            token,
            "koinon_update_catalog",
            {
                "tenant_id": "north",
                "entry_id": initial["id"],
                "expected_updated_at": initial["updated_at"],
                "changes": {"name": "Organized", "metadata": {"tags": ["work"]}},
            },
        )
    )
    stale = call(
        client,
        token,
        "koinon_update_catalog",
        {
            "tenant_id": "north",
            "entry_id": initial["id"],
            "expected_updated_at": initial["updated_at"],
            "changes": {"name": "Overwrite"},
        },
    ).json()["result"]
    assert stale["isError"] and "CATALOG_CHANGED" in str(stale)
    moved = result(
        call(
            client,
            token,
            "koinon_move_folder",
            {
                "tenant_id": "north",
                "entry_id": initial["id"],
                "move": {
                    "parent_id": other["id"],
                    "expected_parent_id": project["id"],
                    "expected_updated_at": updated["updated_at"],
                },
            },
        )
    )
    archived = result(
        call(
            client,
            token,
            "koinon_archive_catalog",
            {"tenant_id": "north", "entry_id": initial["id"], "expected_updated_at": moved["updated_at"]},
        )
    )
    found = result(
        call(
            client,
            token,
            "koinon_list",
            {
                "tenant_id": "north",
                "include_archived": True,
                "status": "archived",
                "tag": "work",
                "sort": "updated_at",
                "order": "desc",
                "parent_id": other["id"],
            },
        )
    )
    assert [row["id"] for row in found["items"]] == [initial["id"]]
    restored = result(
        call(
            client,
            token,
            "koinon_restore_catalog",
            {"tenant_id": "north", "entry_id": initial["id"], "expected_updated_at": archived["updated_at"]},
        )
    )
    assert restored["status"] == "ready"
    denied = call(
        client,
        token,
        "koinon_create_folder",
        {
            "tenant_id": "north",
            "kind": "knowledge_item",
            "name": "Invented publication",
            "parent_id": other["id"],
        },
    ).json()["result"]
    assert denied["isError"]


def test_scope_space_current_role_and_protected_root_guards_stay_authoritative(client):
    project = create(client, "project", client.workspace_id, "Project")
    foreign = client.post(
        "/api/v1/tenants/north/catalog", headers=bearer(), json={"kind": "workspace", "name": "Other"}
    ).json()
    token = create_pat(
        client, "editor", ["catalog:read", "catalog:write"], workspace_ids=[client.workspace_id]
    )["token"]
    args = {"tenant_id": "north", "kind": "project", "name": "Denied", "parent_id": foreign["id"]}
    denied = call(client, token, "koinon_create_folder", args).json()["result"]
    assert denied["isError"] and "mcp/www_authenticate" not in denied.get("_meta", {})
    readonly = create_pat(client, "editor")["token"]
    assert call(client, readonly, "koinon_create_folder", {**args, "parent_id": client.workspace_id}).json()[
        "result"
    ]["isError"]

    async def downgrade():
        repository = client.native_app.state.context.get_bean(MembershipRepository)
        rows = await repository.find_all(subject=ISSUER + "|editor")
        for row in rows:
            row.role = "viewer"
            await repository.save(row)

    client.portal.call(downgrade)
    denied = call(
        client,
        token,
        "koinon_archive_catalog",
        {"tenant_id": "north", "entry_id": project["id"], "expected_updated_at": project["updated_at"]},
    ).json()["result"]
    assert denied["isError"]


def test_primary_oauth_connection_keeps_user_workspace_bounds_for_ordinary_catalog_changes(oauth_client):
    from koinon.mcp_auth.settings import McpOAuthSettings

    oauth_client.native_app.state.context.get_bean(McpOAuthSettings).clients[0]["scopes"].append(
        "catalog:write"
    )
    token = oauth_token(oauth_client, subject="editor", scopes="catalog:read catalog:write")
    value = result(
        call(
            oauth_client,
            token,
            "koinon_create_folder",
            {
                "tenant_id": "north",
                "kind": "project",
                "name": "OAuth project",
                "parent_id": oauth_client.workspace_id,
            },
        )
    )
    assert value["created_by"] == ISSUER + "|editor"
    assert call(
        oauth_client,
        token,
        "koinon_create_folder",
        {"tenant_id": "north", "kind": "workspace", "name": "Too broad"},
    ).json()["result"]["isError"]


async def test_creation_unknown_result_is_not_retried_or_reported_as_known_failure():
    created = []

    async def canonical(request):
        created.append(await request.json())
        await asyncio.Event().wait()
        return JSONResponse({})

    config = settings()
    config.timeout_seconds = 1
    server = create_mcp_server(
        Starlette(routes=[Route("/api/v1/tenants/north/catalog", canonical, methods=["POST"])]), config
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=config.transport_security()
    )
    async with server.session_manager.run(), protocol(app, {"Authorization": "Bearer owned-pat"}) as session:
        value = await session.call_tool(
            "koinon_create_folder", {"tenant_id": "north", "kind": "workspace", "name": "One request"}
        )
        assert value.is_error and "unknown" in str(value).lower() and "do not repeat" in str(value).lower()
    assert len(created) == 1


@pytest.mark.parametrize("client", [{"timeout_seconds": 1}], indirect=True)
def test_real_committed_folder_with_lost_response_remains_unknown_without_replay(client, monkeypatch):
    from koinon.catalog.service import CatalogService

    service = client.native_app.state.context.get_bean(CatalogService)
    original = service.create
    committed = []

    async def delayed(*args, **kwargs):
        value = await original(*args, **kwargs)
        committed.append(value.id)
        await asyncio.Event().wait()
        return value

    monkeypatch.setattr(service, "create", delayed)
    token = create_pat(client, "editor", ["catalog:read", "catalog:write"])["token"]
    value = call(
        client,
        token,
        "koinon_create_folder",
        {"tenant_id": "north", "kind": "project", "name": "Lost response", "parent_id": client.workspace_id},
    ).json()["result"]
    assert value["isError"] and "unknown" in str(value).lower()
    assert len(committed) == 1
    actual = client.get("/api/v1/tenants/north/catalog/" + committed[0], headers=bearer("editor"))
    assert actual.status_code == 200 and actual.json()["name"] == "Lost response"


def test_protected_roots_and_stale_lifecycle_cannot_be_changed_through_tools(client):
    from koinon.catalog.service import CatalogService

    async def provision_fixture():
        service = client.native_app.state.context.get_bean(CatalogService)
        return (
            await service._write_create(
                "system:installation",
                "north",
                kind="workspace",
                name="System",
                system_key="organization",
                installation_run_id="fixture",
            )
        ).id

    identifier = client.portal.call(provision_fixture)
    row = client.get("/api/v1/tenants/north/catalog/" + identifier, headers=bearer()).json()
    token = create_pat(client, scopes=["catalog:read", "catalog:write"])["token"]
    denied = call(
        client,
        token,
        "koinon_archive_catalog",
        {"tenant_id": "north", "entry_id": identifier, "expected_updated_at": row["updated_at"]},
    ).json()["result"]
    assert denied["isError"] and "SYSTEM_SPACE_PROTECTED" in str(denied)
    missing = call(
        client, token, "koinon_archive_catalog", {"tenant_id": "north", "entry_id": identifier}
    ).json()["result"]
    assert missing["isError"]
    assert (
        client.get("/api/v1/tenants/north/catalog/" + identifier, headers=bearer()).json()["status"]
        == "ready"
    )


def test_availability_tool_observes_only_requested_authorized_assets_without_starting_work(client):
    project = create(client, "project", client.workspace_id)
    collection = create(client, "collection", project["id"])
    source = create(client, "source", collection["id"])
    document = create(client, "document", source["id"])
    token = create_pat(client, scopes=["catalog:read"], asset_ids=[document["id"]])["token"]
    observed = result(
        call(
            client,
            token,
            "koinon_availability",
            {
                "tenant_id": "north",
                "selection": {"asset_ids": [document["id"]], "workspace_id": client.workspace_id},
            },
        )
    )
    assert set(observed["items"]) == {document["id"]}
    unrelated = create(client, "document", source["id"], "Unrelated")
    denied = call(
        client,
        token,
        "koinon_availability",
        {"tenant_id": "north", "selection": {"asset_ids": [unrelated["id"]]}},
    ).json()["result"]
    assert denied["isError"]
