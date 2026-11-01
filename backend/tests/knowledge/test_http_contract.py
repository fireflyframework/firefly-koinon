# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import runpy
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

_fixtures = runpy.run_path(str(Path(__file__).parents[1] / "web" / "conftest.py"))
client = _fixtures["client"]
bearer = _fixtures["bearer"]


@pytest.fixture(autouse=True)
def enable_knowledge_routes(monkeypatch):
    import koinon.app

    original = koinon.app.create_application

    def with_knowledge(config):
        config.setdefault("koinon", {})["knowledge"] = {"enabled": True}
        return original(config)

    monkeypatch.setattr(koinon.app, "create_application", with_knowledge)


@pytest.fixture
def hierarchy(client):
    parent = client.workspace_id
    project = None
    for kind in ("project", "collection"):
        response = client.post(
            "/api/v1/tenants/north/catalog",
            headers=bearer(),
            json={"kind": kind, "name": kind, "parent_id": parent},
        )
        assert response.status_code == 201, response.text
        parent = response.json()["id"]
        if kind == "project":
            project = parent
    return {
        "workspace_id": client.workspace_id,
        "project_id": project,
        "parent_id": parent,
        "mode": "document",
    }


def test_upload_http_uses_verified_identity_and_denies_viewer(client, hierarchy, monkeypatch):
    from koinon.knowledge.adapters import NativeDomains

    domains = client.native_app.state.context.get_bean(NativeDomains)
    ensure = AsyncMock(return_value=client.workspace_id)
    ingest = AsyncMock(return_value={"source_id": "native-source", "n_chunks": 1})
    monkeypatch.setattr(domains, "ensure_workspace", ensure)
    monkeypatch.setattr(domains, "ingest_document", ingest)
    denied = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer("viewer"),
        data=hierarchy,
        files={"file": ("facts.txt", b"Facts")},
    )
    assert denied.status_code == 403, denied.text
    ingest.assert_not_awaited()
    response = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers={**bearer(), "X-Actor": "forged"},
        data=hierarchy,
        files={"file": ("facts.txt", b"Facts")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["assets"][0]["kind"] == "document"
    assert ingest.await_args.kwargs["actor"] == _fixtures["ISSUER"] + "|admin"


def test_upload_http_bounds_file_bytes_and_rejects_directory_components(client, hierarchy, monkeypatch):
    from koinon.knowledge.service import KnowledgeFacade

    facade = client.native_app.state.context.get_bean(KnowledgeFacade)
    facade.settings.max_upload_bytes = 4
    response = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data=hierarchy,
        files={"file": ("facts.txt", b"12345")},
    )
    assert response.status_code == 413, response.text
    response = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data=hierarchy,
        files={"file": ("../facts.txt", b"123")},
    )
    assert response.status_code == 400, response.text


def test_common_search_and_query_http_schemas_require_authentication(client):
    assert client.post("/api/v1/tenants/north/search", json={"question": "facts"}).status_code == 401
    bad = client.post(
        "/api/v1/tenants/north/search", headers=bearer(), json={"question": "facts", "limit": 1000}
    )
    assert bad.status_code == 422, bad.text
    denied = client.post("/api/v1/tenants/south/search", headers=bearer(), json={"question": "facts"})
    assert denied.status_code == 403, denied.text


def test_search_asset_scope_http_empty_unknown_and_bounds_never_invoke_a_model(client, monkeypatch):
    from koinon.knowledge.adapters import NativeDomains

    domains = client.native_app.state.context.get_bean(NativeDomains)
    search = AsyncMock()
    monkeypatch.setattr(domains, "search", search)
    response = client.post(
        "/api/v1/tenants/north/search",
        headers=bearer(),
        json={"question": "facts", "asset_ids": [], "answer": True},
    )
    assert response.status_code == 200, response.text
    from koinon.organization_knowledge.dtos import OrganizationKnowledgeSnapshot

    result = response.json()
    policy = OrganizationKnowledgeSnapshot.model_validate(result.pop("knowledge_settings_snapshot"))
    assert policy.tenant_id == "north" and policy.origin == "deployment" and policy.revision == 0
    assert result == {"hits": [], "answer": "", "citations": []}
    response = client.post(
        "/api/v1/tenants/north/search", headers=bearer(), json={"question": "facts", "asset_ids": ["unknown"]}
    )
    assert response.status_code == 403, response.text
    response = client.post(
        "/api/v1/tenants/north/search", headers=bearer(), json={"question": "facts", "asset_ids": ["x"] * 129}
    )
    assert response.status_code == 422, response.text
    search.assert_not_awaited()


def test_document_chunks_and_original_http_are_scoped_and_safe_attachments(client, hierarchy, monkeypatch):
    from koinon.knowledge.adapters import NativeDomains

    domains = client.native_app.state.context.get_bean(NativeDomains)
    monkeypatch.setattr(domains, "ensure_workspace", AsyncMock(return_value=client.workspace_id))
    monkeypatch.setattr(
        domains, "ingest_document", AsyncMock(return_value={"source_id": "native-source", "n_chunks": 1})
    )
    uploaded = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data=hierarchy,
        files={"file": ("facts.txt", b"Facts")},
    ).json()
    identifier = uploaded["assets"][0]["id"]
    chunks = AsyncMock(
        return_value={"items": [{"id": "native-citation", "text": "Facts", "page": 1}], "total": 1}
    )
    original = AsyncMock(
        return_value={
            "content": b"Facts",
            "filename": 'facts"\r\n.html',
            "content_type": "application/octet-stream",
        }
    )
    monkeypatch.setattr(domains, "document_chunks", chunks)
    from hashlib import sha256

    from flycanon.core.services.sources.lineage.dtos import OriginalFileReceipt

    from koinon.knowledge.document_history.native import NativeDocumentHistory

    history = client.native_app.state.context.get_bean(NativeDocumentHistory)
    receipt = OriginalFileReceipt(
        None, sha256(b"Facts").hexdigest(), 5, 'facts"\r\n.html', "application/octet-stream", "a" * 64
    )

    async def copy_original(**scope):
        await original(**scope)
        scope["path"].write_bytes(b"Facts")
        return receipt

    monkeypatch.setattr(history, "original_file", copy_original)
    monkeypatch.setattr(history, "original_identity", AsyncMock(return_value=receipt))
    url = f"/api/v1/tenants/north/documents/{identifier}"
    assert client.get(url + "/chunks").status_code == 401
    response = client.get(url + "/chunks?limit=1&page=1&q=Facts", headers=bearer("viewer"))
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["id"] == "native-citation"
    assert response.json()["source_id"] == uploaded["source"]["id"]
    assert chunks.await_args.kwargs["q"] == "Facts"
    assert client.get(url + "/chunks?limit=101", headers=bearer()).status_code == 400
    response = client.get(url + "/original", headers=bearer("viewer"))
    assert response.status_code == 200 and response.content == b"Facts"
    assert response.headers["content-type"] == "application/octet-stream"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert "%0D%0A" in response.headers["content-disposition"]
    chunks.reset_mock()
    original.reset_mock()
    archived = client.post(
        f"/api/v1/tenants/north/catalog/{hierarchy['parent_id']}/archive", headers=bearer()
    )
    assert archived.status_code == 200, archived.text
    assert client.get(url + "/chunks", headers=bearer("viewer")).status_code == 403
    assert client.get(url + "/original", headers=bearer("viewer")).status_code == 403
    chunks.assert_not_awaited()
    original.assert_not_awaited()


def test_content_http_requires_role_version_and_explicit_chunk_effect(client, hierarchy, monkeypatch):
    from koinon.knowledge.adapters import NativeDomains

    domains = client.native_app.state.context.get_bean(NativeDomains)
    monkeypatch.setattr(domains, "ensure_workspace", AsyncMock(return_value=client.workspace_id))
    monkeypatch.setattr(
        domains, "ingest_document", AsyncMock(return_value={"source_id": "native-source", "n_chunks": 1})
    )
    replacement = AsyncMock(
        return_value={
            "previous_chunk_count": 1,
            "invalidated_chunk_ids": ["previous"],
            "chunk_ids_complete": True,
            "n_chunks": 1,
            "unchanged": False,
        }
    )
    monkeypatch.setattr(domains, "replace_document", replacement)
    monkeypatch.setattr(domains, "document_revision", AsyncMock(return_value=None))
    uploaded = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data=hierarchy,
        files={"file": ("v1.md", b"first")},
    ).json()
    identifier = uploaded["assets"][0]["id"]
    url = f"/api/v1/tenants/north/documents/{identifier}/content"
    assert client.post(url, headers=bearer("viewer"), files={"file": ("v2.md", b"next")}).status_code == 403
    assert client.post(url, headers=bearer(), files={"file": ("v2.md", b"next")}).status_code == 400
    headers = {**bearer(), "If-Match": '"' + "a" * 64 + '"'}
    assert client.post(url, headers=headers, files={"file": ("v2.md", b"next")}).status_code == 400
    replacement.assert_not_awaited()
    response = client.post(
        url,
        headers=headers,
        data={"acknowledge_chunk_invalidation": "true"},
        files={"file": ("v2.md", b"next")},
    )
    assert response.status_code == 201, response.text
    assert response.json()["effects"]["previous_chunk_ids_invalidated"] is True
    assert response.json()["version"]["status"] == "ready"
    assert replacement.await_args.kwargs["expected_sha256"] == "a" * 64
    assert replacement.await_args.kwargs["actor"] == _fixtures["ISSUER"] + "|admin"


def test_document_reingest_http_requires_context_version_and_effect_acknowledgment(
    client, hierarchy, monkeypatch
):
    from koinon.knowledge.adapters import NativeDomains

    domains = client.native_app.state.context.get_bean(NativeDomains)
    monkeypatch.setattr(domains, "ensure_workspace", AsyncMock(return_value=client.workspace_id))
    monkeypatch.setattr(
        domains, "ingest_document", AsyncMock(return_value={"source_id": "native-source", "n_chunks": 1})
    )
    original = AsyncMock(return_value={"filename": "facts.txt", "content": b"stored bytes"})
    replacement = AsyncMock(
        return_value={
            "previous_chunk_count": 1,
            "invalidated_chunk_ids": ["previous"],
            "chunk_ids_complete": True,
            "n_chunks": 1,
            "unchanged": False,
        }
    )
    monkeypatch.setattr(domains, "document_original", original)
    monkeypatch.setattr(domains, "replace_document", replacement)
    monkeypatch.setattr(domains, "document_revision", AsyncMock(return_value=None))
    document = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data=hierarchy,
        files={"file": ("facts.txt", b"stored bytes")},
    ).json()["assets"][0]["id"]
    url = f"/api/v1/tenants/north/documents/{document}/reingest"
    assert (
        client.post(url, headers=bearer("viewer"), json={"acknowledge_chunk_invalidation": True}).status_code
        == 403
    )
    assert (
        client.post(url, headers=bearer(), json={"acknowledge_chunk_invalidation": True}).status_code == 400
    )
    headers = {**bearer(), "If-Match": "a" * 64}
    assert client.post(url, headers=headers, json={}).status_code == 400
    original.assert_not_awaited()
    response = client.post(url, headers=headers, json={"acknowledge_chunk_invalidation": True})
    assert response.status_code == 201, response.text
    assert response.json()["version"]["metadata"]["operation"] == "document.reingest"
    assert replacement.await_args.kwargs["force_reingest"] is True
    assert replacement.await_args.kwargs["content"] == b"stored bytes"
