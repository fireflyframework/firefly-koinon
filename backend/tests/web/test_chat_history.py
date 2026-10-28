# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from conftest import ISSUER, bearer

BASE = "/api/v1/tenants/north/chat"


def thread(client, **values):
    response = client.post(BASE + "/threads", headers=bearer(), json=values)
    assert response.status_code == 201, response.text
    return response.json()


def folder(client, name, parent_id=None, actor="admin"):
    response = client.post(
        BASE + "/folders", headers=bearer(actor), json={"name": name, "parent_id": parent_id}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_private_folders_filtered_history_and_revision_safe_rename(client):
    group = folder(client, "Operations")
    conversation = thread(client, title="Review process", folder_id=group["id"])
    folder_url = BASE + "/folders/" + group["id"]
    assert client.get(folder_url, headers=bearer()).json()["conversation_count"] == 1
    assert client.get(folder_url, headers=bearer("viewer")).status_code == 403
    changed = client.patch(
        folder_url, headers=bearer(), json={"name": "Operations review", "expected_revision": 1}
    )
    assert changed.status_code == 200 and changed.json()["conversation_count"] == 1, changed.text
    page = client.get(
        BASE + "/threads", headers=bearer(), params={"folder_id": group["id"], "q": "review", "page_size": 1}
    )
    assert page.status_code == 200, page.text
    assert page.json()["total"] == 1
    assert page.json()["items"][0]["folder_id"] == group["id"]
    assert conversation["revision"] == 1 and conversation["title_source"] == "manual"
    assert client.get(BASE + "/folders", headers=bearer("viewer")).json()["items"] == []
    url = BASE + "/threads/" + conversation["id"]
    renamed = client.patch(
        url, headers=bearer(), json={"title": "Quarterly review", "folder_id": None, "expected_revision": 1}
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["revision"] == 2 and renamed.json()["folder_id"] is None
    assert (
        client.patch(url, headers=bearer(), json={"title": "Stale", "expected_revision": 1}).status_code
        == 409
    )
    assert client.get(url, headers=bearer("viewer")).status_code == 403
    assert client.get(url.replace("north", "south"), headers=bearer("outsider")).status_code == 403
    assert client.get(url, headers=bearer()).json()["title"] == "Quarterly review"


def test_folder_cycles_foreign_assignment_and_removal_preserve_conversations(client):
    parent = folder(client, "Operations")
    child = folder(client, "Reviews", parent["id"])
    roots = client.get(BASE + "/folders", headers=bearer(), params={"root_only": True})
    assert roots.status_code == 200 and [row["id"] for row in roots.json()["items"]] == [parent["id"]]
    children = client.get(BASE + "/folders", headers=bearer(), params={"parent_id": parent["id"]})
    assert [row["id"] for row in children.json()["items"]] == [child["id"]]
    conversation = thread(client, folder_id=parent["id"])
    cycle = client.patch(
        BASE + "/folders/" + parent["id"],
        headers=bearer(),
        json={"parent_id": child["id"], "expected_revision": 1},
    )
    assert cycle.status_code == 409, cycle.text
    foreign = folder(client, "Private", actor="viewer")
    assert (
        client.patch(
            BASE + "/threads/" + conversation["id"],
            headers=bearer(),
            json={"folder_id": foreign["id"], "expected_revision": 1},
        ).status_code
        == 403
    )
    deleted = client.delete(
        BASE + "/folders/" + parent["id"], headers=bearer(), params={"expected_revision": 1}
    )
    assert deleted.status_code == 204, deleted.text
    preserved = client.get(BASE + "/threads/" + conversation["id"], headers=bearer()).json()
    assert preserved["folder_id"] is None and preserved["revision"] == 2
    children = client.get(BASE + "/folders", headers=bearer()).json()["items"]
    assert [item["name"] for item in children] == ["Reviews"] and children[0]["parent_id"] is None


def test_archive_is_reversible_and_prevents_new_runs(client):
    conversation = thread(client)
    url = BASE + "/threads/" + conversation["id"]
    assert (
        client.patch(url, headers=bearer(), json={"archived": True, "expected_revision": 1}).status_code
        == 200
    )
    assert client.get(BASE + "/threads", headers=bearer()).json()["items"] == []
    archived = client.get(BASE + "/threads", headers=bearer(), params={"status": "archived"}).json()
    assert archived["total"] == 1 and archived["items"][0]["archived_at"]
    denied = client.post(
        url + "/runs",
        headers=bearer(),
        json={"agent_id": "not-needed", "message": "New question", "client_request_id": "archive-check"},
    )
    assert denied.status_code == 409 and denied.json()["code"] == "THREAD_ARCHIVED"
    restored = client.patch(url, headers=bearer(), json={"archived": False, "expected_revision": 2})
    assert restored.status_code == 200 and restored.json()["archived_at"] is None


def test_generated_title_never_overwrites_manual_or_stale_revision(client):
    from koinon.assistants.history.service import ChatHistoryService

    conversation = thread(client)
    history = client.native_app.state.context.get_bean(ChatHistoryService)

    async def apply(title, revision):
        return await history.apply_generated_title(
            f"{ISSUER}|admin", "north", conversation["id"], title, expected_revision=revision
        )

    assert client.portal.call(apply, "Service ownership review", 1) is True
    url = BASE + "/threads/" + conversation["id"]
    generated = client.get(url, headers=bearer()).json()
    assert generated["title_source"] == "ai" and generated["revision"] == 2
    assert (
        client.patch(
            url, headers=bearer(), json={"title": "My own title", "expected_revision": 2}
        ).status_code
        == 200
    )
    assert client.portal.call(apply, "Late AI title", 2) is False
    assert client.portal.call(apply, "Another AI title", 3) is False
    assert client.get(url, headers=bearer()).json()["title"] == "My own title"


def test_folder_scope_cannot_broaden_conversation_and_failed_move_rolls_back(client):
    scoped = client.post(
        BASE + "/folders",
        headers=bearer(),
        json={"name": "Research", "scope": {"workspace_id": client.workspace_id}},
    ).json()
    inherited = thread(client, folder_id=scoped["id"])
    assert inherited["scope"] == {"workspace_id": client.workspace_id}
    broad = thread(client)
    url = BASE + "/threads/" + broad["id"]
    denied = client.patch(
        url,
        headers=bearer(),
        json={"folder_id": scoped["id"], "title": "Should not persist", "expected_revision": 1},
    )
    assert denied.status_code == 403, denied.text
    unchanged = client.get(url, headers=bearer()).json()
    assert unchanged["folder_id"] is None and unchanged["revision"] == 1
    assert unchanged["title"] == "New conversation"
    broad_folder = folder(client, "All knowledge")
    denied = client.patch(
        BASE + "/folders/" + broad_folder["id"],
        headers=bearer(),
        json={"parent_id": scoped["id"], "expected_revision": 1},
    )
    assert denied.status_code == 403


def test_folder_pages_and_invalid_metadata_are_bounded(client):
    for name in ("Review A", "Review B", "Other"):
        folder(client, name)
    response = client.get(
        BASE + "/folders", headers=bearer(), params={"q": "Review", "page_size": 1, "page": 2}
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2 and response.json()["pages"] == 2
    assert response.json()["items"][0]["name"] == "Review B"
    for params in ({"page_size": 101}, {"page": 0}, {"sort": "subject"}):
        assert client.get(BASE + "/folders", headers=bearer(), params=params).status_code == 400
    conversation = thread(client)
    url = BASE + "/threads/" + conversation["id"]
    for patch in ({"title": None}, {"title": "Line\nbreak"}, {"archived": None}, {}):
        assert client.patch(url, headers=bearer(), json={**patch, "expected_revision": 1}).status_code in {
            400,
            422,
        }
    assert client.get(BASE + "/threads", headers=bearer(), params={"status": "deleted"}).status_code == 400


def test_workspace_only_member_can_organize_current_authorized_history(client):
    from koinon.catalog.repositories import MembershipRepository

    async def restrict():
        repository = client.native_app.state.context.get_bean(MembershipRepository)
        membership = await repository.find_by_id("viewer")
        membership.workspace_id = client.workspace_id
        await repository.save(membership)

    client.portal.call(restrict)
    empty = client.get(
        BASE + "/threads", headers=bearer("viewer"), params={"workspace_id": client.workspace_id}
    )
    assert empty.status_code == 200 and empty.json()["total"] == 0, empty.text
    empty_folders = client.get(
        BASE + "/folders", headers=bearer("viewer"), params={"workspace_id": client.workspace_id}
    )
    assert empty_folders.status_code == 200 and empty_folders.json()["total"] == 0, empty_folders.text
    group = client.post(
        BASE + "/folders",
        headers=bearer("viewer"),
        json={"name": "Research", "scope": {"workspace_id": client.workspace_id}},
    )
    assert group.status_code == 201, group.text
    child = client.post(
        BASE + "/folders", headers=bearer("viewer"), json={"name": "Review", "parent_id": group.json()["id"]}
    )
    assert child.status_code == 201, child.text
    listing = client.get(BASE + "/folders", headers=bearer("viewer"))
    assert listing.status_code == 200, listing.text
    assert listing.json()["total"] == 2
