# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path

import httpx

from koinon_sdk import KoinonClient
from koinon_sdk.identity import (
    IdentityProviderInput,
    IdentityProviderPatch,
    KeycloakCredential,
    KeycloakSettings,
)
from koinon_sdk.indexes import IndexCreateInput


def fixtures():
    path = Path(__file__).resolve().parents[2] / "contract/fixtures.json"
    return json.loads(path.read_text())["fixtures"]


async def test_connection_http_preserves_selected_secrets_omission_null_and_index_preconditions():
    values, requests = fixtures(), []
    responses = ["IdentityProvider", "IdentityProvider", "IdentityProvider", "IndexJobView"]

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=values[responses[len(requests) - 1]])

    selected = "selected-caller-secret"
    value = IdentityProviderInput(
        kind="keycloak",
        name="Company",
        settings=KeycloakSettings(kind="keycloak", issuer="https://identity.test/realm", client_id="app"),
        credential=KeycloakCredential(kind="keycloak", secret=selected),
    )
    assert selected not in repr(value)
    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        await client.create_identity_provider("north", value)
        await client.update_identity_provider(
            "north", "p/one", IdentityProviderPatch(expected_revision=2, credential=None)
        )
        await client.update_identity_provider(
            "north", "p/one", IdentityProviderPatch(expected_revision=3, name="Renamed")
        )
        await client.create_knowledge_index(
            "north",
            IndexCreateInput(
                workspace_id="workspace",
                domain="documents",
                provider_id="provider",
                model_id="embed",
                expected_active_id=None,
                expected_connection_revision=None,
            ),
            "stable-key",
        )
    body = [json.loads(request.content) for request in requests]
    assert body[0]["credential"]["secret"] == selected
    assert body[1] == {"expected_revision": 2, "credential": None}
    assert "credential" not in body[2]
    assert body[3]["expected_active_id"] is None and body[3]["expected_connection_revision"] is None
    assert requests[1].url.raw_path.endswith(b"/identity/providers/p%2Fone")
    assert requests[3].headers["Idempotency-Key"] == "stable-key"
    assert all(request.headers["Authorization"] == "Bearer fresh" for request in requests)


async def test_private_binary_filename_and_tool_activity_are_typed():
    from koinon_sdk.models import StreamEvent

    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            200,
            content=b"private bytes",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Disposition": 'attachment; filename="Notes.md"',
                "ETag": '"digest"',
            },
        )

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "supplied", transport=httpx.MockTransport(handle)
    ) as client:
        download = await client.attachment_original("north", "thread", "file/one")
    assert download.filename == "Notes.md" and download.content == b"private bytes"
    assert calls[0].url.raw_path.endswith(b"/attachments/file%2Fone/original")
    event = StreamEvent.model_validate(
        {
            "id": "3",
            "type": "tool_activity",
            "data": {
                "tool_activity": {
                    "call_id": "stable",
                    "tool_name": "inspect_schema",
                    "status": "completed",
                    "occurred_at": "2026-10-27T00:00:00Z",
                    "duration_ms": 12,
                    "summary": "Inspect dataset schema",
                }
            },
        }
    )
    assert event.data.tool_activity is not None and event.data.tool_activity.duration_ms == 12
