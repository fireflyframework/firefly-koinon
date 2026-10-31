# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Personal folder memory is explicit; removed conversations are no longer accessible."""

from conftest import bearer

BASE = "/api/v1/tenants/north/chat"


def test_folder_memory_is_opt_in_private_and_revision_checked(client):
    response = client.post(BASE + "/folders", headers=bearer(), json={"name": "Project review"})
    assert response.status_code == 201
    folder = response.json()
    assert folder["memory_enabled"] is False
    url = BASE + "/folders/" + folder["id"]
    assert (
        client.patch(
            url, headers=bearer("viewer"), json={"memory_enabled": True, "expected_revision": 1}
        ).status_code
        == 403
    )
    enabled = client.patch(url, headers=bearer(), json={"memory_enabled": True, "expected_revision": 1})
    assert enabled.status_code == 200, enabled.text
    assert enabled.json()["memory_enabled"] is True and enabled.json()["revision"] == 2
    assert (
        client.patch(
            url, headers=bearer(), json={"memory_enabled": False, "expected_revision": 1}
        ).status_code
        == 409
    )
    for value in [None, "true", 1]:
        assert client.patch(
            url, headers=bearer(), json={"memory_enabled": value, "expected_revision": 2}
        ).status_code in {400, 422}
    disabled = client.patch(url, headers=bearer(), json={"memory_enabled": False, "expected_revision": 2})
    assert disabled.status_code == 200 and disabled.json()["memory_enabled"] is False


def test_remove_conversation_requires_owner_and_exact_revision_and_retains_records(client):
    from koinon.assistants.entities import ChatMessage
    from koinon.assistants.service import AssistantService

    response = client.post(BASE + "/threads", headers=bearer(), json={"title": "Temporary review"})
    assert response.status_code == 201
    conversation = response.json()
    service = client.native_app.state.context.get_bean(AssistantService)

    async def seed():
        await service.message_repository.save(
            ChatMessage(
                id="retained-message",
                thread_id=conversation["id"],
                role="user",
                text="Preserve the audit record",
            )
        )

    client.portal.call(seed)
    url = BASE + "/threads/" + conversation["id"]
    assert client.delete(url, headers=bearer("viewer"), params={"expected_revision": 1}).status_code == 403
    assert client.delete(url, headers=bearer(), params={"expected_revision": 2}).status_code == 409
    removed = client.delete(url, headers=bearer(), params={"expected_revision": 1})
    assert removed.status_code == 204, removed.text
    for path in [url, url + "/messages"]:
        assert client.get(path, headers=bearer()).status_code == 403
    for status in ["active", "archived", "all"]:
        assert (
            client.get(BASE + "/threads", headers=bearer(), params={"status": status}).json()["items"] == []
        )
    assert (
        client.patch(url, headers=bearer(), json={"archived": False, "expected_revision": 2}).status_code
        == 403
    )

    async def retained():
        row = await service.threads.find_by_id(conversation["id"])
        message = await service.message_repository.find_by_id("retained-message")
        return row.deleted_at is not None, message.text

    assert client.portal.call(retained) == (True, "Preserve the audit record")
