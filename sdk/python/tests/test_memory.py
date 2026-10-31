# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest
from pydantic import ValidationError

from koinon_sdk import FolderPatch, KoinonClient, OrganizationChatSettingsInput, OrganizationMemoryPolicy


def test_memory_inputs_preserve_omission_and_reject_implicit_activation():
    assert FolderPatch(expected_revision=2).model_dump(exclude_unset=True) == {"expected_revision": 2}
    assert OrganizationChatSettingsInput(default_agent_id=None, expected_revision=2).model_dump(
        exclude_unset=True
    ) == {"default_agent_id": None, "expected_revision": 2}
    for invalid in [None, "true", 1]:
        with pytest.raises(ValidationError):
            FolderPatch.model_validate({"expected_revision": 2, "memory_enabled": invalid})
    with pytest.raises(ValidationError):
        OrganizationChatSettingsInput.model_validate(
            {"default_agent_id": None, "expected_revision": 2, "memory": None}
        )
    with pytest.raises(ValidationError):
        OrganizationMemoryPolicy(max_history_messages=10, max_project_memory_messages=11)


async def test_memory_change_and_conversation_delete_keep_explicit_revision_and_false():
    seen = []

    def handle(request):
        seen.append(request)
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(
            200,
            json={
                "id": "folder",
                "name": "Research",
                "parent_id": None,
                "scope": {},
                "revision": 3,
                "conversation_count": 0,
                "memory_enabled": False,
                "created_at": "2026-10-30T00:00:00Z",
                "updated_at": "2026-10-30T00:00:00Z",
            },
        )

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fixture", transport=httpx.MockTransport(handle)
    ) as client:
        saved = await client.update_folder(
            "tenant/one", "folder/one", FolderPatch(expected_revision=2, memory_enabled=False)
        )
        assert saved.memory_enabled is False
        await client.delete_thread("tenant/one", "thread/one", expected_revision=5)
    assert json.loads(seen[0].content) == {"expected_revision": 2, "memory_enabled": False}
    assert seen[1].method == "DELETE"
    assert seen[1].url.path.endswith("/chat/threads/thread/one")
    assert seen[1].url.raw_path.endswith(b"thread%2Fone?expected_revision=5")
