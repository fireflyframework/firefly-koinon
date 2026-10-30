# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

from http_fixtures import bearer
from http_fixtures import client as client
from http_fixtures import oauth_client as oauth_client
from test_mcp_http import call, create_pat


def proposal(client):
    parent = client.workspace_id
    for kind in ("project", "collection"):
        result = client.post(
            "/api/v1/tenants/north/catalog",
            headers=bearer(),
            json={"kind": kind, "name": kind, "parent_id": parent},
        )
        assert result.status_code == 201, result.text
        parent = result.json()["id"]
    return {
        "tenant_id": "north",
        "proposal": {
            "action": "create_draft",
            "destination_id": parent,
            "content": {"title": "External proposal", "body": "Proposed by the external assistant."},
        },
        "idempotency_key": "owned-stage-key",
    }


def test_native_mcp_stage_and_private_refresh_require_same_scoped_credential_and_cancel_exact_review(client):
    arguments = proposal(client)
    token = create_pat(client, scopes=["ingest:write"], workspace_ids=[client.workspace_id])["token"]
    response = call(client, token, "koinon_stage_knowledge", arguments).json()["result"]
    assert response["isError"] is False, response
    public = response["structuredContent"]["review"]
    private = response["_meta"]["koinon/knowledgeReview"]
    nonce = private["nonce"]
    assert len(nonce) == 43 and nonce not in json.dumps(response["structuredContent"])
    assert nonce not in json.dumps(response["content"])
    assert public == private["review"]
    assert public["review"]["evidence"][0]["authority"] == "unverified"
    assert private["presentation"]["product_name"] == "koinon"
    refreshed = call(
        client, token, "koinon_review_status", {"tenant_id": "north", "review_id": public["id"]}
    ).json()["result"]
    second = refreshed["_meta"]["koinon/knowledgeReview"]["nonce"]
    assert second != nonce
    decision = {
        "tenant_id": "north",
        "review_id": public["id"],
        "expected_revision": public["review"]["revision"],
        "authorization_digest": public["review"]["authorization_digest"],
    }
    denied = call(
        client,
        token,
        "koinon_approve_knowledge",
        {**decision, "nonce": nonce, "idempotency_key": "owned-approval"},
    ).json()["result"]
    assert denied["isError"] is True
    cancelled = call(client, token, "koinon_cancel_knowledge", {**decision, "nonce": second}).json()["result"]
    assert cancelled["isError"] is False and cancelled["structuredContent"]["status"] == "cancelled"


def test_read_only_pat_and_different_credential_cannot_obtain_another_reviews_private_challenge(client):
    arguments = proposal(client)
    readonly = create_pat(client)["token"]
    denied = call(client, readonly, "koinon_stage_knowledge", arguments).json()["result"]
    assert denied["isError"] is True
    owner = create_pat(client, scopes=["ingest:write"])["token"]
    staged = call(client, owner, "koinon_stage_knowledge", arguments).json()["result"]
    assert staged["isError"] is False, staged
    other = create_pat(client, scopes=["ingest:write"])["token"]
    denied = call(
        client,
        other,
        "koinon_review_status",
        {"tenant_id": "north", "review_id": staged["structuredContent"]["review"]["id"]},
    ).json()["result"]
    assert denied["isError"] is True and "koinon/knowledgeReview" not in denied.get("_meta", {})


def test_oauth_write_scope_upgrade_creates_only_a_review_bound_to_authorized_application(oauth_client):
    from test_mcp_scope_upgrade import oauth_token

    from koinon.mcp_auth.settings import McpOAuthSettings

    arguments = proposal(oauth_client)
    settings = oauth_client.native_app.state.context.get_bean(McpOAuthSettings)
    settings.clients[0]["scopes"].extend(["catalog:write", "ingest:write"])
    readonly = oauth_token(oauth_client)
    denied = call(oauth_client, readonly, "koinon_stage_knowledge", arguments).json()["result"]
    assert denied["isError"] is True
    assert 'scope="catalog:read catalog:write ingest:write"' in denied["_meta"]["mcp/www_authenticate"][0]
    permitted = oauth_token(oauth_client, scopes="ingest:write")
    result = call(oauth_client, permitted, "koinon_stage_knowledge", arguments).json()["result"]
    assert result["isError"] is False, result
    view = result["structuredContent"]["review"]
    assert view["status"] == "preview" and view["review"]["receipt"] is None
    applications = oauth_client.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
    active = next(row for row in applications if row["status"] == "active")
    assert {"catalog:read", "catalog:write", "ingest:write"} <= set(active["scopes"])


def test_prepare_file_upload_resolves_real_destination_and_returns_only_in_chat_setup(client, tmp_path):
    from koinon.knowledge.attachments.storage import AttachmentStorage

    root = tmp_path / "owned-configured-review-storage"
    root.mkdir(mode=0o700)
    client.native_app.state.context.get_bean(AttachmentStorage).settings.storage_root = str(root)
    arguments = proposal(client)
    token = create_pat(client, scopes=["ingest:write"], workspace_ids=[client.workspace_id])["token"]
    result = call(
        client,
        token,
        "koinon_prepare_file_upload",
        {"tenant_id": "north", "destination_id": arguments["proposal"]["destination_id"], "mode": "dataset"},
    ).json()["result"]
    assert result["isError"] is False, result
    setup = result["structuredContent"]["setup"]
    assert setup["tenant_id"] == "north" and setup["destination_name"] == "collection"
    assert setup["max_file_bytes"] == 33554432 and setup["chunk_bytes"] == 65536
    assert result["_meta"]["koinon/knowledgeReview"]["kind"] == "file_upload"
    readonly = create_pat(client)["token"]
    denied = call(
        client,
        readonly,
        "koinon_prepare_file_upload",
        {"tenant_id": "north", "destination_id": arguments["proposal"]["destination_id"], "mode": "dataset"},
    ).json()["result"]
    assert denied["isError"] is True


def test_file_prepare_scope_denial_can_relink_only_when_current_oauth_client_allows_write_scopes(
    oauth_client,
):
    from test_mcp_scope_upgrade import oauth_token

    from koinon.mcp_auth.settings import McpOAuthSettings

    arguments = proposal(oauth_client)
    oauth_client.native_app.state.context.get_bean(McpOAuthSettings).clients[0]["scopes"].extend(
        ["catalog:write", "ingest:write"]
    )
    token = oauth_token(oauth_client)
    result = call(
        oauth_client,
        token,
        "koinon_prepare_file_upload",
        {"tenant_id": "north", "destination_id": arguments["proposal"]["destination_id"], "mode": "document"},
    ).json()["result"]
    assert result["isError"] is True
    assert "mcp/www_authenticate" in result.get("_meta", {})


def test_connection_descriptor_projects_registered_clients_without_secret_or_hash(oauth_client):
    from koinon.mcp_auth.settings import McpOAuthSettings

    configuration = oauth_client.native_app.state.context.get_bean(McpOAuthSettings)
    configuration.clients[0]["client_secret_hash"] = "a" * 64
    response = oauth_client.get("/api/v1/mcp/connection", headers=bearer())
    assert response.status_code == 200
    assert response.json()["clients"] == [
        {
            "client_id": "scope-client",
            "name": "Scope Client",
            "scopes": configuration.clients[0]["scopes"],
            "client_auth": "confidential",
        }
    ]
    assert "a" * 64 not in response.text and "client_secret_hash" not in response.text


def test_native_mcp_file_bytes_are_staged_verified_and_cancelled_without_repository_ingestion(
    client, tmp_path
):
    import base64
    import hashlib

    from koinon.catalog.repositories import CatalogRepository
    from koinon.knowledge.attachments.storage import AttachmentStorage

    private_root = tmp_path / "owned-private-review-bytes"
    private_root.mkdir(mode=0o700)
    client.native_app.state.context.get_bean(AttachmentStorage).settings.storage_root = str(private_root)
    arguments = proposal(client)
    token = create_pat(client, scopes=["ingest:write"], workspace_ids=[client.workspace_id])["token"]
    content = b"Owned selected bytes."
    manifest = {
        "filename": "owned.txt",
        "content_type": "text/plain",
        "mode": "document",
        "destination_id": arguments["proposal"]["destination_id"],
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    staged = call(
        client,
        token,
        "koinon_stage_file",
        {"tenant_id": "north", "file": manifest, "idempotency_key": "owned-file-stage"},
    ).json()["result"]
    assert staged["isError"] is False, staged
    initial = staged["structuredContent"]["review"]
    assert initial["status"] == "uploading" and initial["tenant_id"] == "north"
    old_nonce = staged["_meta"]["koinon/knowledgeReview"]["nonce"]
    received = call(
        client,
        token,
        "koinon_upload_file_chunk",
        {
            "tenant_id": "north",
            "review_id": initial["id"],
            "chunk": {
                "index": 0,
                "data_base64": base64.b64encode(content).decode(),
                "sha256": manifest["sha256"],
            },
        },
    ).json()["result"]
    assert received["isError"] is False and received["structuredContent"]["review"]["received_chunks"] == 1
    sealed = call(
        client, token, "koinon_seal_file", {"tenant_id": "north", "review_id": initial["id"]}
    ).json()["result"]
    assert sealed["isError"] is False, sealed
    current = sealed["structuredContent"]["review"]
    assert current["status"] == "preview" and current["sha256"] == manifest["sha256"]
    nonce = sealed["_meta"]["koinon/knowledgeReview"]["nonce"]
    assert nonce != old_nonce and nonce not in json.dumps(sealed["structuredContent"])
    decision = {
        "tenant_id": "north",
        "review_id": current["id"],
        "expected_revision": current["revision"],
        "authorization_digest": current["authorization_digest"],
        "nonce": nonce,
    }
    result = call(client, token, "koinon_cancel_file", decision).json()["result"]
    assert result["isError"] is False and result["structuredContent"]["review"]["status"] == "cancelled"

    async def sources():
        return await client.native_app.state.context.get_bean(CatalogRepository).find_all(
            tenant_id="north", kind="source"
        )

    assert client.portal.call(sources) == []
