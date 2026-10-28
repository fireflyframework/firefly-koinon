# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from conftest import bearer


def create_token(client, scopes, **changes):
    return client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "SDK integration",
            "tenant_id": "north",
            "scopes": scopes,
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            **changes,
        },
    )


def test_personal_token_secret_is_one_time_scopes_and_revocation_are_enforced(client):
    created = create_token(client, ["catalog:read"])
    assert created.status_code == 201, created.text
    secret, token_id = created.json()["token"], created.json()["id"]
    headers = {"Authorization": "Bearer " + secret}
    assert client.get("/api/v1/context", headers=headers).status_code == 200
    assert (
        client.post(
            "/api/v1/tenants/north/catalog", headers=headers, json={"kind": "workspace", "name": "Denied"}
        ).status_code
        == 403
    )
    listed = client.get("/api/v1/tokens", headers=bearer())
    assert secret not in listed.text and "token_hash" not in listed.text
    assert client.get("/api/v1/tokens", headers=headers).status_code == 403
    assert client.delete("/api/v1/tokens/" + token_id, headers=bearer()).status_code == 204
    assert client.get("/api/v1/context", headers=headers).status_code == 401


def test_personal_token_cannot_exceed_current_role_tenant_or_workspace(client):
    request = {
        "name": "Escalation",
        "tenant_id": "north",
        "scopes": ["members:write"],
        "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    assert client.post("/api/v1/tokens", headers=bearer("viewer"), json=request).status_code == 403
    created = create_token(client, ["catalog:read"], workspace_ids=[client.workspace_id])
    assert created.status_code == 201, created.text
    headers = {"Authorization": "Bearer " + created.json()["token"]}
    assert client.get("/api/v1/tenants/south/catalog", headers=headers).status_code == 403
    assert (
        client.get("/api/v1/tenants/north/catalog/" + client.workspace_id, headers=headers).status_code == 200
    )
    second = client.post(
        "/api/v1/tenants/north/catalog", headers=bearer(), json={"kind": "workspace", "name": "Other"}
    ).json()
    assert client.get("/api/v1/tenants/north/catalog/" + second["id"], headers=headers).status_code == 403


def test_asset_scoped_token_filters_sql_counts_and_cannot_write_ancestors(client):
    parent = client.workspace_id
    for kind in ("project", "collection", "source"):
        parent = client.post(
            "/api/v1/tenants/north/catalog",
            headers=bearer(),
            json={"kind": kind, "name": kind, "parent_id": parent},
        ).json()["id"]
    documents = [
        client.post(
            "/api/v1/tenants/north/catalog",
            headers=bearer(),
            json={"kind": "document", "name": name, "parent_id": parent},
        ).json()
        for name in ("Allowed", "Other")
    ]
    created = create_token(client, ["catalog:write"], asset_ids=[documents[0]["id"]])
    assert created.status_code == 201, created.text
    headers = {"Authorization": "Bearer " + created.json()["token"]}
    page = client.get("/api/v1/tenants/north/catalog?kind=document&page_size=1", headers=headers).json()
    assert page["total"] == 1 and page["items"][0]["id"] == documents[0]["id"]
    assert (
        client.get("/api/v1/tenants/north/catalog/" + documents[1]["id"], headers=headers).status_code == 403
    )
    assert (
        client.patch(
            "/api/v1/tenants/north/catalog/" + parent, headers=headers, json={"name": "Broader source"}
        ).status_code
        == 403
    )
    assert (
        client.patch(
            "/api/v1/tenants/north/catalog/" + documents[0]["id"], headers=headers, json={"name": "Updated"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/v1/tenants/north/catalog", headers=headers, json={"kind": "workspace", "name": "Escalation"}
        ).status_code
        == 403
    )


def test_expired_token_and_membership_revocation_apply_without_renewing_token(client):
    from koinon.tokens.repositories import PersonalTokenRepository

    created = create_token(client, ["catalog:read"])
    secret, token_id = created.json()["token"], created.json()["id"]

    async def expire():
        repository = client.native_app.state.context.get_bean(PersonalTokenRepository)
        row = await repository.find_by_id(token_id)
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await repository.save(row)

    client.portal.call(expire)
    assert client.get("/api/v1/context", headers={"Authorization": "Bearer " + secret}).status_code == 401

    fresh = create_token(client, ["catalog:read"])
    from koinon.catalog.repositories import MembershipRepository

    async def revoke_membership():
        repository = client.native_app.state.context.get_bean(MembershipRepository)
        member = await repository.find_by_id("admin")
        member.active = False
        await repository.save(member)

    client.portal.call(revoke_membership)
    assert (
        client.get(
            "/api/v1/tenants/north/catalog",
            headers={
                "Authorization": "Bearer " + fresh.json()["token"],
            },
        ).status_code
        == 403
    )


def test_revoked_delegated_token_stops_durable_chat_before_any_model_call(client):
    from conftest import ISSUER

    from koinon.assistants.execution import AssistantExecutor
    from koinon.assistants.queue import AssistantQueue
    from koinon.assistants.service import AssistantService
    from koinon.assistants.settings import AssistantSettings

    context = client.native_app.state.context

    async def setup():
        context.get_bean(AssistantSettings).allowed_provider_hosts = ["127.0.0.1"]
        service = context.get_bean(AssistantService)
        provider = await service.save_provider(
            ISSUER + "|admin",
            "north",
            {
                "name": "Controlled provider",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["test-model"],
            },
        )
        return await service.save_agent(
            ISSUER + "|admin",
            "north",
            {
                "name": "Controlled guide",
                "provider_id": provider["id"],
                "model_id": "test-model",
                "tools": [],
            },
        )

    agent = client.portal.call(setup)
    token = create_token(client, ["chat:use"]).json()
    headers = {"Authorization": "Bearer " + token["token"]}
    thread = client.post("/api/v1/tenants/north/chat/threads", headers=headers, json={}).json()
    run = client.post(
        "/api/v1/tenants/north/chat/threads/" + thread["id"] + "/runs",
        headers=headers,
        json={"agent_id": agent["id"], "message": "Question", "client_request_id": "delegated-worker"},
    ).json()
    assert client.delete("/api/v1/tokens/" + token["id"], headers=bearer()).status_code == 204

    async def execute():
        service = context.get_bean(AssistantService)
        claimed = await context.get_bean(AssistantQueue).claim("delegated-worker")
        assert claimed.id == run["run_id"] and claimed.access_token_id == token["id"]
        await context.get_bean(AssistantExecutor).execute(claimed.id, "delegated-worker")
        return await service.runs.find_by_id(claimed.id)

    stopped = client.portal.call(execute)
    assert stopped.status == "failed" and stopped.error_code == "TOKEN_UNAVAILABLE"
