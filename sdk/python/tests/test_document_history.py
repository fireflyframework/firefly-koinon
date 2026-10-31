# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256

import httpx

from koinon_sdk import KoinonClient


async def test_exact_history_helpers_encode_every_identity_and_preserve_part_digests():
    seen = []
    content = dict(
        document_id="d/1",
        catalog_source_id="catalog",
        native_source_id="native",
        source_version_id="v/1",
        extraction_id="e/1",
        source_part_id="p/1",
        kind="chunk",
        text="retained",
        sha256=sha256(b"retained").hexdigest(),
        recorded_page=7,
        page_basis="recorded_loader",
        raw_sha256="a" * 64,
        normalized_sha256="b" * 64,
        input_sha256="b" * 64,
    )

    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/original"):
            return httpx.Response(200, content=b"raw", headers={"ETag": '"raw-digest"'})
        return httpx.Response(200, json=content)

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "reader",
        transport=httpx.MockTransport(handle),
    ) as client:
        part = await client.document_part("t/1", "d/1", "v/1", "e/1", "p/1")
        original = await client.document_version_original("t/1", "d/1", "v/1")
    assert part.source_part_id == "p/1" and part.recorded_page == 7
    assert part.sha256 == sha256(part.text.encode()).hexdigest()
    assert original.content == b"raw"
    assert (
        seen[0].url.raw_path
        == b"/api/v1/tenants/t%2F1/documents/d%2F1/versions/v%2F1/extractions/e%2F1/parts/p%2F1"
    )
    assert seen[1].url.raw_path.endswith(b"/versions/v%2F1/original")
    assert all(request.headers["authorization"] == "Bearer reader" for request in seen)


async def test_all_history_metadata_helpers_preserve_tuples_and_page_filters():
    from datetime import UTC, datetime

    seen = []
    identity = dict(document_id="document", catalog_source_id="catalog", native_source_id="native")
    stamp = datetime.now(UTC).isoformat()
    version = dict(
        **identity,
        source_version_id="version",
        filename="old.txt",
        media_type="text/plain",
        sha256="a" * 64,
        byte_size=1,
        actor="owner",
        created_at=stamp,
    )
    extraction = dict(
        **identity,
        source_version_id="version",
        extraction_id="extraction",
        purpose="ingestion",
        coverage="complete",
        normalized_sha256="b" * 64,
        created_at=stamp,
    )
    summary = dict(
        **identity,
        source_version_id="version",
        extraction_id="extraction",
        source_part_id="part",
        kind="chunk",
        ordinal=0,
        sha256="c" * 64,
        created_at=stamp,
    )

    def handle(request):
        seen.append(request)
        path = request.url.path
        if path.endswith("/version"):
            return httpx.Response(200, json=version)
        row = summary if path.endswith("/parts") else extraction if path.endswith("/extractions") else version
        return httpx.Response(
            200,
            json=dict(items=[row], total=1, page=2, page_size=5, pages=1, has_next=False, has_previous=True),
        )

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "reader",
        transport=httpx.MockTransport(handle),
    ) as client:
        versions = await client.document_versions("tenant", "document", page=2, page_size=5)
        selected = await client.document_version("tenant", "document", "version")
        extractions = await client.document_extractions("tenant", "document", "version", page=2, page_size=5)
        parts = await client.document_parts(
            "tenant", "document", "version", "extraction", kind="chunk", page=2, page_size=5
        )
    assert versions.items[0].source_version_id == selected.source_version_id == "version"
    assert extractions.items[0].extraction_id == parts.items[0].extraction_id == "extraction"
    assert dict(seen[0].url.params) == {"page": "2", "page_size": "5"}
    assert seen[2].url.path.endswith("/versions/version/extractions")
    assert dict(seen[3].url.params) == {"page": "2", "page_size": "5", "kind": "chunk"}
