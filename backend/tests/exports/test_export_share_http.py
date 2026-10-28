# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "export_share_web_fixture", Path(__file__).resolve().parents[1] / "web/conftest.py"
)
assert spec and spec.loader
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)
client = native.client


def selected_message(client):
    from koinon.assistants.entities import ChatMessage
    from koinon.assistants.repositories import ChatMessageRepository

    headers = native.bearer("viewer")
    thread = client.post(
        "/api/v1/tenants/north/chat/threads", headers=headers, json={"title": "Reviewed notes"}
    )
    assert thread.status_code == 201, thread.text
    thread_id = thread.json()["id"]

    async def seed():
        await client.native_app.state.context.get_bean(ChatMessageRepository).save(
            ChatMessage(
                id="reviewed-user-message",
                thread_id=thread_id,
                role="user",
                text="Exact reviewed notes",
                status="completed",
            )
        )

    client.portal.call(seed)
    return headers, {"thread_id": thread_id, "message_ids": ["reviewed-user-message"]}


def test_native_authenticated_review_export_download_and_cancel(client):
    headers, selection = selected_message(client)
    base = "/api/v1/tenants/north/exports"
    preview = client.post(
        base + "/reviews", headers=headers, json={**selection, "kind": "conversation", "format": "json"}
    )
    assert preview.status_code == 201, preview.text
    assert preview.json()["messages"][0]["text"] == "Exact reviewed notes"
    created = client.post(
        base,
        headers=headers,
        json={"review_id": preview.json()["id"], "expected_revision": preview.json()["revision"]},
    )
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    download = client.get(base + "/" + identifier + "/download", headers=headers)
    assert download.status_code == 200, download.text
    assert json.loads(download.content)["messages"][0]["text"] == "Exact reviewed notes"
    assert download.headers["cache-control"] == "no-store"
    assert download.headers["x-content-type-options"] == "nosniff"
    assert download.headers["content-disposition"].endswith('.json"')
    assert download.headers["etag"].startswith('"')
    assert client.get(base + "/" + identifier + "/download", headers=native.bearer()).status_code == 403
    assert client.get(base, headers=headers, params={"q": "Reviewed", "page_size": 1}).json()["total"] == 1
    assert client.delete(base + "/" + identifier, headers=headers).status_code == 204
    assert client.get(base + "/" + identifier, headers=headers).json()["status"] == "cancelled"
    assert client.get(base + "/" + identifier + "/download", headers=headers).status_code == 403


def test_native_current_acl_share_and_source_manifest(client):
    headers, selection = selected_message(client)
    evidence = client.post("/api/v1/tenants/north/evidence/conversations", headers=headers, json=selection)
    assert evidence.status_code == 200, evidence.text
    assert evidence.json()["complete"] is True and evidence.json()["sources"] == []
    base = "/api/v1/tenants/north/shares"
    preview = client.post(base + "/reviews", headers=headers, json=selection)
    assert preview.status_code == 201, preview.text
    created = client.post(
        base,
        headers=headers,
        json={"review_id": preview.json()["id"], "expected_revision": preview.json()["revision"]},
    )
    assert created.status_code == 201, created.text
    identifier = created.json()["id"]
    opened = client.get(base + "/" + identifier, headers=native.bearer())
    assert opened.status_code == 200 and opened.json()["messages"][0]["text"] == "Exact reviewed notes"
    assert client.get(base + "/" + identifier, headers=native.bearer("outsider")).status_code == 403
    assert client.get(base + "/" + identifier).status_code == 401
    assert client.delete(base + "/" + identifier, headers=native.bearer()).status_code == 403
    assert client.delete(base + "/" + identifier, headers=headers).status_code == 204
    revoked = client.get(base + "/" + identifier, headers=native.bearer())
    assert revoked.status_code == 410 and revoked.json()["code"] == "SHARE_REVOKED"
    assert "no-store" in revoked.headers["cache-control"]


def test_explicit_pat_share_scopes_are_supported_and_revoke_invalidates_later_reads(client):
    from datetime import UTC, datetime, timedelta

    headers, selection = selected_message(client)
    token = client.post(
        "/api/v1/tokens",
        headers=headers,
        json={
            "name": "Reviewed share automation",
            "tenant_id": "north",
            "scopes": ["shares:read", "shares:write"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert token.status_code == 201, token.text
    authority = {"Authorization": "Bearer " + token.json()["token"]}
    base = "/api/v1/tenants/north/shares"
    preview = client.post(base + "/reviews", headers=authority, json=selection)
    assert preview.status_code == 201, preview.text
    assert "no-store" in preview.headers["cache-control"]
    shared = client.post(
        base,
        headers=authority,
        json={"review_id": preview.json()["id"], "expected_revision": preview.json()["revision"]},
    )
    assert shared.status_code == 201, shared.text
    identifier = shared.json()["id"]
    assert client.get(base + "/" + identifier, headers=native.bearer()).status_code == 200
    assert client.delete("/api/v1/tokens/" + token.json()["id"], headers=headers).status_code == 204
    assert client.get(base + "/" + identifier, headers=native.bearer()).status_code == 403
    owned = client.get(base, headers=headers)
    assert owned.status_code == 200, owned.text
    assert owned.json()["items"][0]["id"] == identifier
    assert client.delete(base + "/" + identifier, headers=headers).status_code == 204


def test_review_discriminator_validates_native_wire_body_and_keeps_missing_provider_actionable(client):
    headers, selection = selected_message(client)
    base = "/api/v1/tenants/north/exports/reviews"
    for body in (
        {**selection, "kind": "conversation", "format": "pdf"},
        {**selection, "kind": "conversation", "format": "json", "storage_url": "file:///private"},
        {**selection, "format": "json"},
    ):
        assert client.post(base, headers=headers, json=body).status_code == 422
    missing = client.post(
        base,
        headers=headers,
        json={"kind": "query_result", "dataset_id": "dataset", "query_id": "query", "format": "parquet"},
    )
    assert missing.status_code == 503, missing.text
    assert "STORED_RESULT_UNAVAILABLE" in missing.text
