# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native PAT write boundaries over owned SQLite and a controlled ingestion port."""

import socket
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from conftest import ISSUER, bearer

PREFIX = "/api/v1/tenants/north"
ADMIN = [
    "catalog:read",
    "catalog:write",
    "ingest:write",
    "providers:write",
    "agents:write",
    "members:write",
    "settings:write",
    "jobs:manage",
    "audit:read",
    "chat:use",
]


@pytest.fixture(autouse=True)
def native_upload_slice(monkeypatch, request):
    if "workspace_pat_can_upload" not in request.node.name:
        return
    import koinon.app
    from koinon.knowledge.adapters import NativeDomains
    from koinon.knowledge.controllers import KnowledgeController
    from koinon.knowledge.document_history.downloads import OriginalDownloads
    from koinon.knowledge.repositories import DomainBindingRepository
    from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings
    from koinon.web.projection import register_controller

    original = koinon.app.create_application

    def application(config):
        app = original(config)
        context = app.state.context
        context.register_bean(DomainBindingRepository)
        context.container.register_instance(NativeDomains, SimpleNamespace())
        context.container.register_instance(KnowledgeSettings, KnowledgeSettings())
        context.container.register_instance(
            OriginalDownloads,
            SimpleNamespace(open=AsyncMock(side_effect=AssertionError("Uploads must not invoke downloads"))),
        )
        context.register_bean(KnowledgeFacade)
        register_controller(context, KnowledgeController)
        return app

    monkeypatch.setattr(koinon.app, "create_application", application)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("External socket operation forbidden in owned HTTP fixtures")

    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


def checked(label, response, expected):
    assert response.status_code == expected, (label, response.status_code, response.text)
    return response.json() if response.content else None


def issue(client, scopes, **bounds):
    value = checked(
        "interactive user issues explicit PAT",
        client.post(
            "/api/v1/tokens",
            headers=bearer(),
            json={
                "name": "Owned write proof",
                "tenant_id": "north",
                "scopes": scopes,
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
                **bounds,
            },
        ),
        201,
    )
    return value, {"Authorization": "Bearer " + value["token"]}


def tree(client, headers, workspace=None):
    parent = workspace or client.workspace_id
    result = {}
    for kind in ("project", "collection"):
        value = checked(
            "PAT creates " + kind,
            client.post(
                PREFIX + "/catalog",
                headers=headers,
                json={"kind": kind, "name": "Owned " + kind, "parent_id": parent},
            ),
            201,
        )
        result[kind] = value["id"]
        parent = value["id"]
    return result


def test_admin_scope_inventory_and_pat_catalog_crud(client):
    options = checked(
        "interactive scope inventory",
        client.get("/api/v1/tokens/scopes", headers=bearer(), params={"tenant_id": "north"}),
        200,
    )
    assert set(ADMIN) <= {row["id"] for row in options["items"]}
    token, headers = issue(client, ADMIN)
    checked("PAT authenticates as current user", client.get("/api/v1/context", headers=headers), 200)
    workspace = checked(
        "PAT creates workspace",
        client.post(
            PREFIX + "/catalog", headers=headers, json={"kind": "workspace", "name": "Owned workspace"}
        ),
        201,
    )
    child = tree(client, headers, workspace["id"])
    edited = checked(
        "PAT updates project",
        client.patch(
            PREFIX + "/catalog/" + child["project"], headers=headers, json={"name": "Updated by PAT"}
        ),
        200,
    )
    assert edited["name"] == "Updated by PAT" and edited["updated_by"] == ISSUER + "|admin"
    checked(
        "PAT archives collection",
        client.post(PREFIX + "/catalog/" + child["collection"] + "/archive", headers=headers),
        200,
    )
    checked(
        "PAT restores collection",
        client.post(PREFIX + "/catalog/" + child["collection"] + "/restore", headers=headers),
        200,
    )
    checked(
        "PAT deletes empty collection",
        client.delete(PREFIX + "/catalog/" + child["collection"], headers=headers),
        204,
    )
    checked(
        "PAT cannot mint another token",
        client.post(
            "/api/v1/tokens",
            headers=headers,
            json={
                "name": "Chaining denied",
                "tenant_id": "north",
                "scopes": ["catalog:read"],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        ),
        403,
    )


def test_admin_pat_provider_agent_settings_membership_writes(client):
    from koinon.assistants.settings import AssistantSettings

    client.native_app.state.context.get_bean(AssistantSettings).allowed_provider_hosts = ["127.0.0.1"]
    token, headers = issue(client, ADMIN)
    provider = checked(
        "PAT saves provider without connectivity claim",
        client.post(
            PREFIX + "/providers",
            headers=headers,
            json={
                "name": "Owned unverified provider",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": ["owned-no-model-call"],
            },
        ),
        201,
    )
    checked(
        "PAT edits provider metadata",
        client.put(
            PREFIX + "/providers/" + provider["id"], headers=headers, json={"name": "Updated provider"}
        ),
        200,
    )
    agent = checked(
        "PAT saves agent without model invocation",
        client.post(
            PREFIX + "/agents",
            headers=headers,
            json={
                "name": "Owned guide",
                "provider_id": provider["id"],
                "model_id": "owned-no-model-call",
                "tools": ["search_knowledge"],
                "scope": {},
            },
        ),
        201,
    )
    checked(
        "PAT edits agent metadata",
        client.patch(
            PREFIX + "/agents/" + agent["id"],
            headers=headers,
            json={"description": "Configured by scoped authority"},
        ),
        200,
    )
    branding = checked(
        "PAT saves organization branding",
        client.put(
            PREFIX + "/branding",
            headers=headers,
            json={"expected_revision": 0, "branding": {"product_name": "Owned PAT identity"}},
        ),
        200,
    )
    assert branding["revision"] == 1
    checked(
        "PAT saves organization chat default",
        client.put(
            PREFIX + "/chat/settings",
            headers=headers,
            json={"default_agent_id": agent["id"], "expected_revision": 0},
        ),
        200,
    )
    member = checked(
        "PAT creates membership",
        client.post(
            PREFIX + "/members",
            headers=headers,
            json={"subject": ISSUER + "|owned-api-member", "role": "viewer"},
        ),
        201,
    )
    checked(
        "PAT updates membership",
        client.patch(PREFIX + "/members/" + member["id"], headers=headers, json={"role": "editor"}),
        200,
    )
    checked(
        "PAT removes membership", client.delete(PREFIX + "/members/" + member["id"], headers=headers), 204
    )
    checked(
        "PAT cannot write another organization",
        client.post(
            "/api/v1/tenants/south/providers",
            headers=headers,
            json={
                "name": "Denied",
                "kind": "ollama",
                "base_url": "http://127.0.0.1:11434/v1",
                "model_ids": [],
            },
        ),
        403,
    )


@pytest.mark.parametrize("mode", ["document", "dataset"])
def test_workspace_pat_can_upload_through_native_http_and_scope_is_checked_before_port(client, mode):
    from koinon.knowledge.service import KnowledgeFacade

    token, headers = issue(client, ["ingest:write"], workspace_ids=[client.workspace_id])
    assert {"catalog:read", "catalog:write", "ingest:write"} <= set(token["scopes"])
    context = tree(client, headers)
    calls = []

    async def ingest(**values):
        assert values["actor"] == ISSUER + "|admin" and values["tenant_id"] == "north"
        assert values["content"] == b"Owned input bytes, controlled native port only."
        if "authorize_commit" in values:
            await values["authorize_commit"]()
        calls.append(
            {
                "domain": mode,
                "tenant": values["tenant_id"],
                "actor": values["actor"],
                "bytes_sha256": sha256(values["content"]).hexdigest(),
            }
        )
        return {
            "source_id": "owned-native-source",
            "dataset_id": "owned-native-dataset",
            "file_id": "owned-native-file",
            "tables": [],
        }

    domains = SimpleNamespace(
        ensure_workspace=AsyncMock(return_value="owned-native-workspace"),
        ingest_document=AsyncMock(side_effect=ingest),
        ingest_dataset=AsyncMock(side_effect=ingest),
    )
    client.native_app.state.context.get_bean(KnowledgeFacade).domains = domains
    fields = {
        "workspace_id": client.workspace_id,
        "project_id": context["project"],
        "parent_id": context["collection"],
        "mode": mode,
    }
    result = checked(
        "workspace PAT canonical multipart " + mode,
        client.post(
            PREFIX + "/sources/upload",
            headers=headers,
            data=fields,
            files={"file": ("owned.txt", b"Owned input bytes, controlled native port only.", "text/plain")},
        ),
        201,
    )
    assert result["source"]["created_by"] == ISSUER + "|admin" and result["assets"][0]["kind"] == mode
    assert result["source"]["status"] == "ready" and len(calls) == 1
    checked(
        "workspace PAT foreign organization upload denied",
        client.post(
            "/api/v1/tenants/south/sources/upload",
            headers=headers,
            data=fields,
            files={"file": ("owned.txt", b"Owned input bytes, controlled native port only.", "text/plain")},
        ),
        403,
    )
    readonly, read_headers = issue(client, ["catalog:read"], workspace_ids=[client.workspace_id])
    checked(
        "read-only PAT upload denied before native port",
        client.post(
            PREFIX + "/sources/upload",
            headers=read_headers,
            data=fields,
            files={"file": ("owned.txt", b"Owned input bytes, controlled native port only.", "text/plain")},
        ),
        403,
    )
    assert len(calls) == 1


def test_write_pat_current_role_downgrade_revoke_and_expiry_apply(client):
    token, headers = issue(client, ADMIN)
    checked(
        "keep another real organization administrator",
        client.post(
            PREFIX + "/members",
            headers=bearer(),
            json={"subject": ISSUER + "|owned-second-admin", "role": "admin"},
        ),
        201,
    )
    checked(
        "interactive role downgrade",
        client.patch(PREFIX + "/members/admin", headers=bearer(), json={"role": "viewer"}),
        200,
    )
    checked(
        "existing PAT cannot retain old catalog write role",
        client.post(
            PREFIX + "/catalog", headers=headers, json={"kind": "workspace", "name": "Denied after downgrade"}
        ),
        403,
    )
    checked(
        "existing PAT cannot retain old settings role",
        client.put(PREFIX + "/branding", headers=headers, json={"expected_revision": 0, "branding": {}}),
        403,
    )
    checked(
        "interactive owner revokes existing PAT",
        client.delete("/api/v1/tokens/" + token["id"], headers=bearer()),
        204,
    )
    checked("revoked PAT cannot authenticate", client.get("/api/v1/context", headers=headers), 401)
    expired, expired_headers = issue(client, ["catalog:read"])
    from koinon.tokens.repositories import PersonalTokenRepository

    async def expire():
        repo = client.native_app.state.context.get_bean(PersonalTokenRepository)
        row = await repo.find_by_id(expired["id"])
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await repo.save(row)

    client.portal.call(expire)
    checked("expired PAT cannot authenticate", client.get("/api/v1/context", headers=expired_headers), 401)


def test_workspace_write_pat_cannot_escape_workspace_or_mint_management_scope(client):
    token, headers = issue(client, ["catalog:write"], workspace_ids=[client.workspace_id])
    tree(client, headers)
    other = checked(
        "interactive creates different workspace",
        client.post(PREFIX + "/catalog", headers=bearer(), json={"kind": "workspace", "name": "Other scope"}),
        201,
    )
    checked(
        "workspace write PAT cannot create cross-workspace child",
        client.post(
            PREFIX + "/catalog",
            headers=headers,
            json={"kind": "project", "name": "Denied crossing", "parent_id": other["id"]},
        ),
        403,
    )
    checked(
        "organization management scope cannot be disguised as workspace-limited",
        client.post(
            "/api/v1/tokens",
            headers=bearer(),
            json={
                "name": "Denied mixed scope",
                "tenant_id": "north",
                "scopes": ["providers:write"],
                "workspace_ids": [client.workspace_id],
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        ),
        400,
    )


def test_jobs_management_scope_can_cancel_a_job_without_knowledge_ingest_permission(client):
    from koinon.jobs.service import JobService

    async def seed():
        job = await client.native_app.state.context.get_bean(JobService).submit(
            "north", client.workspace_id, "ingest", {}, "owned-pat-job"
        )
        return job.id

    identifier = client.portal.call(seed)
    token, headers = issue(client, ["jobs:manage", "catalog:read"])
    assert "ingest:write" not in token["scopes"]
    checked(
        "advertised jobs manage PAT cancels durable job",
        client.post(PREFIX + "/jobs/" + identifier + "/cancel", headers=headers),
        200,
    )
