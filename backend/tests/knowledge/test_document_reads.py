# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from test_facade import context as context
from test_facade import upload


async def test_document_chunks_authorize_ancestry_and_binding_before_native_read(context):
    from koinon.catalog.errors import AccessDenied

    facade, catalog, domains, tree, _ = context
    result = await upload(context)
    document = result["assets"][0]["id"]
    domains.document_chunks = AsyncMock(return_value={"items": [{"id": "native-chunk"}], "total": 1})
    response = await facade.document_chunks("issuer|reader", "north", document, limit=1)
    assert response["document_id"] == document
    assert response["source_id"] == result["source"]["id"]
    assert response["items"][0]["id"] == "native-chunk"
    assert domains.document_chunks.await_args.kwargs["source_id"] == "native-source"
    assert domains.document_chunks.await_args.kwargs["actor"] == "issuer|reader"
    domains.document_chunks.reset_mock()
    for subject, tenant in (("issuer|outsider", "north"), ("issuer|reader", "south")):
        with pytest.raises(AccessDenied):
            await facade.document_chunks(subject, tenant, document)
    await catalog.archive("issuer|admin", "north", tree["collection"].id)
    with pytest.raises(AccessDenied, match="archived"):
        await facade.document_chunks("issuer|reader", "north", document)
    domains.document_chunks.assert_not_awaited()


async def test_document_read_bounds_and_kind_are_checked_before_native_access(context):
    from pyfly.kernel import InvalidRequestException

    from koinon.catalog.errors import InvalidHierarchy

    facade, _, domains, _, _ = context
    result = await upload(context, "dataset")
    domains.document_chunks = AsyncMock()
    with pytest.raises(InvalidHierarchy):
        await facade.document_chunks("issuer|reader", "north", result["assets"][0]["id"])
    document = (await upload(context))["assets"][0]["id"]
    for arguments in (
        {"limit": 101},
        {"limit": 0},
        {"offset": -1},
        {"offset": 100001},
        {"page": 0},
        {"q": "x" * 513},
    ):
        with pytest.raises(InvalidRequestException):
            await facade.document_chunks("issuer|reader", "north", document, **arguments)
    domains.document_chunks.assert_not_awaited()


@pytest.fixture
async def native_document(tmp_path):
    from flycanon.core.services.storage.object_store import ObjectStore
    from flycanon.models.entities import Base
    from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
    from flycanon.models.entities.source import SourceRow
    from flycanon.models.repositories import ChunkRepository, SourceRepository
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.knowledge.adapters import NativeDomains

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'reads.db'}")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    objects = SimpleNamespace(get=AsyncMock(return_value=b"original"))

    async def bounded_read(key, max_bytes):
        return await objects.get(key)

    objects.get_bounded = AsyncMock(side_effect=bounded_read)
    sources, chunks = SourceRepository(sessions), ChunkRepository(sessions)
    beans = {SourceRepository: sources, ChunkRepository: chunks, ObjectStore: objects}
    adapter = NativeDomains(
        SimpleNamespace(contains_type=lambda kind: kind in beans, resolve=beans.__getitem__)
    )
    async with sessions.begin() as session:
        session.add(
            SourceRow(
                id="source",
                tenant_id="north",
                workspace_id="workspace",
                kind="text",
                status="ingested",
                filename="facts.txt",
                content_sha256=sha256(b"original").hexdigest(),
                content_bytes=8,
                object_store_key="north/workspace/files/source.txt",
                n_chunks=4,
            )
        )
        for index, (tenant, page, section, content) in enumerate(
            (
                ("north", 1, "Approval > Rules", "Threshold 42"),
                ("north", 1, "Approval > Rules", "Threshold 43"),
                ("north", 2, "Review", "Literal 100%_safe"),
                ("south", 1, "Approval > Rules", "Foreign secret"),
            )
        ):
            session.add(
                KnowledgeChunkRow(
                    id=f"chunk-{index}",
                    tenant_id=tenant,
                    workspace_id="workspace",
                    source_id="source",
                    index_in_source=index,
                    total_chunks=4,
                    content=content,
                    page=page,
                    section_path=section,
                    char_start=index * 20,
                    char_end=index * 20 + len(content),
                )
            )
    statements = []
    event.listen(
        engine.sync_engine,
        "before_cursor_execute",
        lambda connection, cursor, statement, parameters, context, executemany: statements.append(statement),
    )
    try:
        yield adapter, sources, objects, statements
    finally:
        await engine.dispose()


async def test_native_chunks_filter_and_paginate_in_sql_with_explicit_scope(native_document):
    adapter, _, _, statements = native_document
    arguments = {
        "tenant_id": "north",
        "workspace_id": "workspace",
        "source_id": "source",
        "actor": "issuer|reader",
    }
    response = await adapter.document_chunks(
        **arguments, offset=1, limit=1, page=1, section="Approval", q="Threshold"
    )
    assert response["total"] == 2 and response["next_offset"] is None
    assert [item["id"] for item in response["items"]] == ["chunk-1"]
    assert response["items"][0]["section_path"] == "Approval > Rules"
    assert any(
        "LIMIT" in statement
        and "OFFSET" in statement
        and "tenant_id" in statement
        and "source_id" in statement
        for statement in statements
    )
    assert (await adapter.document_chunks(**arguments, offset=0, limit=50, page=None, section=None, q="%_"))[
        "total"
    ] == 1
    assert (await adapter.document_chunks(**arguments, offset=0, limit=50, page=3, section=None, q=None))[
        "items"
    ] == []


async def test_original_requires_scoped_persisted_bytes_size_and_digest(native_document):
    from pyfly.kernel import PayloadTooLargeException, ResourceNotFoundException, ServiceUnavailableException

    adapter, _, objects, _ = native_document
    arguments = {
        "tenant_id": "north",
        "workspace_id": "workspace",
        "source_id": "source",
        "actor": "issuer|reader",
    }
    result = await adapter.document_original(**arguments, max_bytes=32)
    assert result == {
        "content": b"original",
        "filename": "facts.txt",
        "content_type": "application/octet-stream",
    }
    objects.get.reset_mock()
    with pytest.raises(PayloadTooLargeException):
        await adapter.document_original(**arguments, max_bytes=4)
    objects.get.assert_not_awaited()
    with pytest.raises(ResourceNotFoundException):
        await adapter.document_original(**{**arguments, "tenant_id": "south"}, max_bytes=32)
    objects.get.assert_not_awaited()
    objects.get.return_value = b"tampered"
    with pytest.raises(ServiceUnavailableException, match="integrity"):
        await adapter.document_original(**arguments, max_bytes=32)


async def test_original_integrity_uses_original_metadata_instead_of_normalized_content(native_document):
    adapter, sources, _, _ = native_document
    source = await sources.get("source", tenant_id="north", workspace_id="workspace")
    source.content_sha256 = sha256(b"normalized extraction").hexdigest()
    source.content_bytes = 21
    source.metadata_json = {"_persisted_original": {"sha256": sha256(b"original").hexdigest(), "bytes": 8}}
    await sources.update(source)
    assert (
        await adapter.document_original(
            tenant_id="north",
            workspace_id="workspace",
            source_id="source",
            actor="issuer|reader",
            max_bytes=32,
        )
    )["content"] == b"original"
