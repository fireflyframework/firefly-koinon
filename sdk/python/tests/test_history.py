# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx

from koinon_sdk import KoinonClient, ThreadPatch


async def test_history_wire_preserves_revision_null_restore_false_and_title_omission():
    seen = []
    thread = {
        "id": "thread",
        "title": "Research",
        "title_source": "default",
        "revision": 2,
        "folder_id": None,
        "archived_at": None,
        "scope": {},
        "created_at": "2026-10-27T00:00:00Z",
        "updated_at": "2026-10-27T00:00:00Z",
    }

    def handle(request):
        seen.append(request)
        return httpx.Response(200, json=thread)

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        assert (await client.thread("tenant/one", "thread/one")).revision == 2
        await client.update_thread(
            "tenant/one", "thread/one", ThreadPatch(expected_revision=2, folder_id=None, archived=False)
        )
        await client.create_thread("tenant/one")
    assert json.loads(seen[1].content) == {"expected_revision": 2, "folder_id": None, "archived": False}
    assert "title" not in json.loads(seen[2].content)


async def test_folder_details_paging_reparent_and_revision_delete_are_typed():
    from koinon_sdk import FolderCreate, FolderPatch, TitleRequest

    seen = []
    folder = {
        "id": "folder",
        "name": "Research",
        "parent_id": None,
        "scope": {},
        "revision": 2,
        "conversation_count": 3,
        "created_at": "2026-10-27T00:00:00Z",
        "updated_at": "2026-10-27T00:00:00Z",
    }

    def handle(request):
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        if request.url.path.endswith("/title-suggestion"):
            return httpx.Response(200, json={"title": "Suggested", "based_on_revision": 2})
        value = (
            {"items": [folder], "total": 1, "page": 1, "page_size": 25}
            if request.method == "GET" and request.url.path.endswith("/folders")
            else folder
        )
        return httpx.Response(200, json=value)

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        assert (await client.folders("t", root_only=True, workspace_id="w")).items[0].conversation_count == 3
        await client.create_folder("t", FolderCreate(name="Research"))
        await client.update_folder("t", "folder/one", FolderPatch(expected_revision=2, parent_id=None))
        assert (await client.folder("t", "folder/one")).revision == 2
        await client.delete_folder("t", "folder/one", expected_revision=2)
        assert (
            await client.suggest_title("t", "thread", TitleRequest(agent_id="agent", expected_revision=2))
        ).based_on_revision == 2
    assert dict(seen[0].url.params) == {"root_only": "true", "workspace_id": "w"}
    assert json.loads(seen[2].content) == {"expected_revision": 2, "parent_id": None}
    assert dict(seen[4].url.params) == {"expected_revision": "2"}
