# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent application contexts share initialization facts, never SDK transports."""

import json
from contextlib import contextmanager
from copy import deepcopy
from datetime import UTC, datetime, timedelta

import pytest
from http_fixtures import bearer
from http_fixtures import client as client
from http_fixtures import oauth_client as oauth_client
from starlette.testclient import TestClient
from test_mcp_http import HEADERS, create_pat
from test_mcp_legacy_sessions import initialize, legacy_call
from test_mcp_review_http import proposal

from koinon.app import create_application


@contextmanager
def replica(client):
    first = client.native_app.state.context
    app = create_application(deepcopy(first.config.to_dict()))
    with TestClient(app) as second:
        second.native_app = app
        second.workspace_id = client.workspace_id
        yield second


@pytest.fixture
def peer(client):
    with replica(client) as second:
        yield second


def test_legacy_initialization_survives_another_application(client, peer):
    token = create_pat(client)["token"]
    session = initialize(client, token)
    response = legacy_call(peer, token, session, "koinon_context", {})
    assert response.status_code == 200, response.text
    assert response.json()["result"]["isError"] is False
    assert client.native_app.state.context is not peer.native_app.state.context


def test_origin_shutdown_leaves_session_usable_by_a_fresh_successor(client):
    token = create_pat(client)["token"]
    with replica(client) as origin:
        session = initialize(origin, token)
    with replica(client) as successor:
        result = legacy_call(successor, token, session, "koinon_context", {})
        assert result.status_code == 200 and result.json()["result"]["isError"] is False


def test_private_review_nonce_rotation_and_decision_survive_replica_routing(client, peer):
    values = proposal(client)
    token = create_pat(client, scopes=["ingest:write"], workspace_ids=[client.workspace_id])["token"]
    session = initialize(client, token)
    staged = legacy_call(peer, token, session, "koinon_stage_knowledge", values).json()["result"]
    assert staged["isError"] is False
    view = staged["structuredContent"]["review"]
    nonce = staged["_meta"]["koinon/knowledgeReview"]["nonce"]
    assert nonce not in json.dumps(staged["structuredContent"]) and nonce not in json.dumps(staged["content"])
    refresh = legacy_call(
        client, token, session, "koinon_review_status", {"tenant_id": "north", "review_id": view["id"]}
    ).json()["result"]
    current = refresh["_meta"]["koinon/knowledgeReview"]["nonce"]
    assert current != nonce
    decision = {
        "tenant_id": "north",
        "review_id": view["id"],
        "expected_revision": view["review"]["revision"],
        "authorization_digest": view["review"]["authorization_digest"],
    }
    denied = legacy_call(
        peer,
        token,
        session,
        "koinon_approve_knowledge",
        {**decision, "nonce": nonce, "idempotency_key": "old-nonce"},
    ).json()["result"]
    assert denied["isError"] is True
    cancelled = legacy_call(
        peer, token, session, "koinon_cancel_knowledge", {**decision, "nonce": current}
    ).json()["result"]
    assert cancelled["isError"] is False and cancelled["structuredContent"]["status"] == "cancelled"


def test_stored_apps_cannot_cross_credentials_or_mask_current_pat_revocation(client, peer):
    first, other = create_pat(client), create_pat(client)
    session = initialize(client, first["token"])
    assert legacy_call(peer, other["token"], session, "koinon_context", {}).status_code == 404
    assert client.delete("/api/v1/tokens/" + first["id"], headers=bearer()).status_code == 204
    denied = legacy_call(peer, first["token"], session, "koinon_context", {})
    assert denied.status_code == 401 and "koinon/knowledgeReview" not in denied.text


def test_current_membership_denies_private_payload_after_cross_replica_initialization(client, peer):
    from koinon.catalog.repositories import MembershipRepository

    values = proposal(client)
    token = create_pat(client, scopes=["ingest:write"])["token"]
    session = initialize(client, token)

    async def downgrade():
        repository = client.native_app.state.context.get_bean(MembershipRepository)
        row = await repository.find_by_id("admin")
        row.role = "viewer"
        await repository.save(row)

    client.portal.call(downgrade)
    denied = legacy_call(peer, token, session, "koinon_stage_knowledge", values)
    assert denied.status_code == 200 and denied.json()["result"]["isError"]
    assert "koinon/knowledgeReview" not in denied.json()["result"].get("_meta", {})


def test_delete_and_expiry_are_global_and_do_not_resurrect(client, peer):
    from pyfly.data.relational.framework_schema import mcp_sessions
    from pyfly.data.transaction import TransactionTemplate
    from pyfly.mcp import McpSessionStore
    from sqlalchemy import update

    token = create_pat(client)["token"]
    session = initialize(client, token)
    peer.cookies.clear()
    deleted = peer.delete(
        "/mcp",
        headers={
            **HEADERS,
            "Authorization": "Bearer " + token,
            "Mcp-Session-Id": session,
            "MCP-Protocol-Version": "2025-11-25",
        },
    )
    assert deleted.status_code == 204
    assert legacy_call(client, token, session, "koinon_context", {}).status_code == 404
    expired = initialize(client, token)

    async def expire():
        store = client.native_app.state.context.get_bean(McpSessionStore)
        async with TransactionTemplate(store.datasource).transaction() as unit:
            await unit.resource.execute(
                update(mcp_sessions)
                .where(mcp_sessions.c.session_id == expired)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )

    client.portal.call(expire)
    assert legacy_call(peer, token, expired, "koinon_context", {}).status_code == 404
    assert legacy_call(client, token, expired, "koinon_context", {}).status_code == 404


def test_oauth_application_revocation_is_current_on_another_replica(oauth_client):
    from test_mcp_scope_upgrade import oauth_token

    token = oauth_token(oauth_client)
    session = initialize(oauth_client, token)
    with replica(oauth_client) as second:
        result = legacy_call(second, token, session, "koinon_context", {})
        assert result.status_code == 200 and result.json()["result"]["isError"] is False
        apps = oauth_client.get("/api/v1/authorized-applications", headers=bearer()).json()["items"]
        active = next(value for value in apps if value["status"] == "active")
        assert (
            oauth_client.delete(
                "/api/v1/authorized-applications/" + active["id"], headers=bearer()
            ).status_code
            == 204
        )
        denied = legacy_call(second, token, session, "koinon_context", {})
        assert denied.status_code == 401


@pytest.mark.parametrize("client", [{"max_sessions": 1}], indirect=True)
def test_session_admission_limit_is_shared_across_applications(client, peer):
    token = create_pat(client)["token"]
    initialize(client, token)
    peer.cookies.clear()
    result = peer.post(
        "/mcp",
        headers={**HEADERS, "Authorization": "Bearer " + token},
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "clientInfo": {"name": "second", "version": "1"},
                "capabilities": {},
            },
        },
    )
    assert result.status_code == 503
