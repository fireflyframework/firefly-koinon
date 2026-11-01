# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Signed in-process HTTP and native DI with a controlled read-only ledger port."""

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from unittest.mock import AsyncMock

from flycanon.core.services.sources.lineage.dtos import OriginalFileReceipt
from test_http_contract import bearer as bearer
from test_http_contract import client as client
from test_http_contract import enable_knowledge_routes as enable_knowledge_routes
from test_http_contract import hierarchy as hierarchy

from koinon.knowledge.adapters import NativeDomains
from koinon.knowledge.document_history.native import NativeDocumentHistory


def prepared(client, hierarchy, monkeypatch):
    context = client.native_app.state.context
    domains = context.get_bean(NativeDomains)
    monkeypatch.setattr(domains, "ensure_workspace", AsyncMock(return_value=client.workspace_id))
    monkeypatch.setattr(
        domains, "ingest_document", AsyncMock(return_value={"source_id": "native", "n_chunks": 1})
    )
    uploaded = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data=hierarchy,
        files={"file": ("current-name.txt", b"Current")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()["assets"][0]["id"]
    reader = context.get_bean(NativeDocumentHistory)
    stamp = datetime(2026, 10, 1, tzinfo=UTC)
    digest = sha256(b"retained").hexdigest()
    version = dict(
        source_version_id="version",
        filename="historical.txt",
        media_type="text/plain",
        sha256=digest,
        byte_size=8,
        actor="historical-owner",
        created_at=stamp,
        predecessor_source_version_id=None,
    )
    extraction = dict(
        source_version_id="version",
        extraction_id="extraction",
        purpose="ingestion",
        coverage="complete",
        normalized_sha256=digest,
        created_at=stamp,
        predecessor_extraction_id=None,
    )
    summary = dict(
        source_version_id="version",
        extraction_id="extraction",
        source_part_id="part",
        kind="chunk",
        ordinal=0,
        sha256=digest,
        recorded_page=7,
        page_basis="recorded_loader",
        created_at=stamp,
        char_start=0,
        char_end=8,
        offset_basis="section",
    )
    part = dict(
        source_version_id="version",
        extraction_id="extraction",
        source_part_id="part",
        kind="chunk",
        sha256=digest,
        text="retained",
        recorded_page=7,
        page_basis="recorded_loader",
        raw_sha256=digest,
        normalized_sha256=digest,
        input_sha256=digest,
    )

    def page(row):
        return dict(items=(row,), total=1, page=1, page_size=25, pages=1, has_next=False, has_previous=False)

    methods = dict(
        versions=page(version),
        version=version,
        extractions=page(extraction),
        parts=page(summary),
        part=part,
    )
    reads = {}
    for name, value in methods.items():
        reads[name] = AsyncMock(return_value=value)
        monkeypatch.setattr(reader, name, reads[name])
    receipt = OriginalFileReceipt("version", digest, 8, 'historical"\r\n.html', "text/html", "a" * 64)

    async def copy_original(**scope):
        scope["path"].write_bytes(b"retained")
        return receipt

    reads["original_file"] = AsyncMock(side_effect=copy_original)
    reads["original_identity"] = AsyncMock(return_value=receipt)
    monkeypatch.setattr(reader, "original_file", reads["original_file"])
    monkeypatch.setattr(reader, "original_identity", reads["original_identity"])
    path = f"/api/v1/tenants/north/documents/{document}/versions"
    return path, document, reads


def test_all_exact_document_history_routes_use_verified_current_scope(client, hierarchy, monkeypatch):
    path, document, reads = prepared(client, hierarchy, monkeypatch)
    suffixes = (
        "",
        "/version",
        "/version/extractions",
        "/version/extractions/extraction/parts",
        "/version/extractions/extraction/parts/part",
        "/version/original",
    )
    for suffix in suffixes:
        assert client.get(path + suffix).status_code == 401
        denied = client.get((path + suffix).replace("/north/", "/south/"), headers=bearer())
        assert denied.status_code == 403, denied.text
        response = client.get(path + suffix, headers=bearer("viewer"))
        assert response.status_code == 200, response.text
        if suffix.endswith("original"):
            assert response.content == b"retained"
            assert response.headers["cache-control"] == "private, no-store"
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["etag"] == '"' + sha256(b"retained").hexdigest() + '"'
            assert "%0D%0A" in response.headers["content-disposition"]
        else:
            row = response.json()
            if "items" in row:
                row = row["items"][0]
            assert row["document_id"] == document and row["native_source_id"] == "native"
            assert not {"object_key", "projection_chunk_id", "implementation", "projection"} & row.keys()
    assert reads["version"].await_args.kwargs["source_version_id"] == "version"
    assert reads["part"].await_args.kwargs["source_part_id"] == "part"
    for name, read in reads.items():
        assert read.await_count >= 1 if name == "original_identity" else read.await_count == 1
        assert read.await_args.kwargs["actor"].endswith("|viewer")
        assert read.await_args.kwargs["workspace_id"] == client.workspace_id


def test_history_pat_scope_validation_and_post_read_revocation(client, hierarchy, monkeypatch):
    from koinon.tokens.repositories import PersonalTokenRepository

    path, _, reads = prepared(client, hierarchy, monkeypatch)
    for suffix in ("", "/version/extractions", "/version/extractions/extraction/parts"):
        assert client.get(path + suffix, params={"page_size": 101}, headers=bearer()).status_code == 400
    for read in reads.values():
        read.assert_not_awaited()
    issued = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "historical read",
            "tenant_id": "north",
            "scopes": ["catalog:read"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert issued.status_code == 201, issued.text
    token = issued.json()
    headers = {"Authorization": "Bearer " + token["token"]}
    assert client.get(path + "/version", headers=headers).status_code == 200
    repository = client.native_app.state.context.get_bean(PersonalTokenRepository)
    original_result = reads["version"].return_value

    async def revoke_during_read(**scope):
        row = await repository.find_by_id(token["id"])
        row.revoked_at = datetime.now(UTC)
        await repository.save(row)
        return original_result

    reads["version"].side_effect = revoke_during_read
    revoked = client.get(path + "/version", headers=headers)
    assert revoked.status_code == 403, revoked.text
    assert "historical.txt" not in revoked.text


def test_archiving_an_ancestor_during_exact_content_read_denies_the_result(client, hierarchy, monkeypatch):
    from koinon.catalog.service import CatalogService

    path, _, reads = prepared(client, hierarchy, monkeypatch)
    catalog = client.native_app.state.context.get_bean(CatalogService)
    result = reads["part"].return_value

    async def archive_during_read(**scope):
        await catalog.archive(
            "https://identity.example.test/realms/koinon|admin",
            "north",
            hierarchy["parent_id"],
        )
        return result

    reads["part"].side_effect = archive_during_read
    response = client.get(path + "/version/extractions/extraction/parts/part", headers=bearer("viewer"))
    assert response.status_code == 403, response.text
    assert "retained" not in response.text


def test_original_download_refuses_insufficient_shared_scratch_before_object_io(
    client, hierarchy, monkeypatch
):
    from koinon.knowledge.document_history.downloads import OriginalDownloads
    from koinon.storage.scratch import ScratchAdmission

    path, _, reads = prepared(client, hierarchy, monkeypatch)
    context = client.native_app.state.context
    scratch = context.get_bean(ScratchAdmission)
    scratch.capacity_bytes = 8
    response = client.get(path + "/version/original", headers=bearer("viewer"))
    assert response.status_code == 413, response.text
    reads["original_file"].assert_not_awaited()
    assert scratch.available_bytes == 8
    assert context.get_bean(OriginalDownloads).slots.available_slots == 1


def test_pat_revocation_during_owned_file_copy_returns_no_original_and_releases_capacity(
    client, hierarchy, monkeypatch
):
    from koinon.knowledge.document_history.downloads import OriginalDownloads
    from koinon.storage.scratch import ScratchAdmission
    from koinon.tokens.repositories import PersonalTokenRepository

    path, _, reads = prepared(client, hierarchy, monkeypatch)
    issued = client.post(
        "/api/v1/tokens",
        headers=bearer(),
        json={
            "name": "original",
            "tenant_id": "north",
            "scopes": ["catalog:read"],
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        },
    )
    assert issued.status_code == 201, issued.text
    token = issued.json()
    context = client.native_app.state.context
    tokens = context.get_bean(PersonalTokenRepository)
    paths = []
    original_copy = reads["original_file"].side_effect

    async def revoke(**scope):
        receipt = await original_copy(**scope)
        paths.append(scope["path"])
        row = await tokens.find_by_id(token["id"])
        row.revoked_at = datetime.now(UTC)
        await tokens.save(row)
        return receipt

    reads["original_file"].side_effect = revoke
    response = client.get(path + "/version/original", headers={"Authorization": "Bearer " + token["token"]})
    assert response.status_code == 403, response.text
    assert b"retained" not in response.content
    assert paths and not paths[0].exists()
    assert (
        context.get_bean(ScratchAdmission).available_bytes
        == context.get_bean(ScratchAdmission).capacity_bytes
    )
    assert context.get_bean(OriginalDownloads).slots.available_slots == 1


def test_changed_pinned_original_before_stream_release_denies_without_losing_scratch(
    client, hierarchy, monkeypatch
):
    from dataclasses import replace

    from koinon.storage.scratch import ScratchAdmission

    path, _, reads = prepared(client, hierarchy, monkeypatch)
    receipt = reads["original_identity"].return_value
    reads["original_identity"].side_effect = [receipt, replace(receipt, anchor="b" * 64)]
    response = client.get(path + "/version/original", headers=bearer("viewer"))
    assert response.status_code == 403, response.text
    assert b"retained" not in response.content
    scratch = client.native_app.state.context.get_bean(ScratchAdmission)
    assert scratch.available_bytes == scratch.capacity_bytes
