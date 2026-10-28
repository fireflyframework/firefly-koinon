# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from test_http_contract import bearer as bearer
from test_http_contract import client as client
from test_http_contract import enable_knowledge_routes as enable_knowledge_routes
from test_http_contract import hierarchy as hierarchy

from koinon.knowledge.adapters import NativeDomains


@pytest.mark.parametrize("operation", ("content", "reingest"))
def test_document_mutation_requires_exact_pair_and_rejects_malformed_headers(
    client, hierarchy, monkeypatch, operation
):
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
    original = AsyncMock(return_value={"filename": "facts.txt", "content": b"stored bytes"})
    monkeypatch.setattr(domains, "replace_document", replacement)
    monkeypatch.setattr(domains, "document_original", original)
    version, extraction = str(uuid4()), str(uuid4())
    monkeypatch.setattr(
        domains,
        "document_revision",
        AsyncMock(return_value={"source_version_id": version, "extraction_id": extraction}),
    )
    response = client.post(
        "/api/v1/tenants/north/sources/upload",
        headers=bearer(),
        data=hierarchy,
        files={"file": ("facts.txt", b"stored bytes")},
    )
    assert response.status_code == 201
    document = response.json()["assets"][0]["id"]
    path = f"/api/v1/tenants/north/documents/{document}/{operation}"

    def send(extra):
        options = (
            {"json": {"acknowledge_chunk_invalidation": True}}
            if operation == "reingest"
            else {
                "data": {"acknowledge_chunk_invalidation": "true"},
                "files": {"file": ("next.txt", b"next bytes")},
            }
        )
        return client.post(path, headers={**bearer(), "If-Match": "a" * 64, **extra}, **options)

    for headers in (
        {"X-Koinon-Source-Version": "invalid", "X-Koinon-Extraction": extraction},
        {"X-Koinon-Source-Version": version},
        {"X-Koinon-Extraction": extraction},
        {"X-Koinon-Source-Version": version, "X-Koinon-Extraction": "invalid"},
    ):
        response = send(headers)
        assert response.status_code == 422, response.text
        assert response.json()["code"] == "VALIDATION_ERROR"
    for headers, code in (
        ({}, "DOCUMENT_VERSION_REQUIRED"),
        (
            {"X-Koinon-Source-Version": str(uuid4()), "X-Koinon-Extraction": extraction},
            "DOCUMENT_VERSION_CONFLICT",
        ),
        (
            {"X-Koinon-Source-Version": version, "X-Koinon-Extraction": str(uuid4())},
            "DOCUMENT_VERSION_CONFLICT",
        ),
    ):
        response = send(headers)
        assert response.status_code == 409, response.text
        assert response.json()["code"] == code
    replacement.assert_not_awaited()
    original.assert_not_awaited()
    response = send({"X-Koinon-Source-Version": version.upper(), "X-Koinon-Extraction": extraction.upper()})
    assert response.status_code == 201, response.text
    assert replacement.await_args.kwargs["expected_source_version_id"] == version
    assert replacement.await_args.kwargs["expected_extraction_id"] == extraction
    assert replacement.await_args.kwargs["expected_sha256"] == "a" * 64
