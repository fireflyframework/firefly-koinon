# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from hashlib import sha256
from types import SimpleNamespace

import pytest
from pyfly.kernel import InvalidRequestException, ResourceNotFoundException
from sqlalchemy import event, insert, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def history(tmp_path):
    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.models.entities.source_lineage import (
        metadata,
        source_artifacts,
        source_events,
        source_extractions,
        source_parts,
        source_versions,
    )

    from koinon.knowledge.document_history.native import NativeDocumentHistory
    from koinon.knowledge.document_history.repositories import DocumentHistoryRepository
    from koinon.knowledge.document_history.resources import DocumentHistoryResources

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'history.db'}")
    sessions = async_sessionmaker(engine)

    @asynccontextmanager
    async def session():
        async with sessions() as value:
            yield value

    raw = b"historical original"
    objects = {"private-object-key": raw, "normalized-key": b"retained text"}

    async def get_bounded(key, max_bytes):
        return objects[key]

    lineage = DocumentLineage(SimpleNamespace(session=session), SimpleNamespace(get_bounded=get_bounded))
    common = dict(tenant_id="tenant", workspace_id="workspace", source_id="source")
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(
            insert(source_artifacts),
            [
                dict(
                    id="artifact",
                    **common,
                    role="raw",
                    sha256=sha256(raw).hexdigest(),
                    bytes=len(raw),
                    object_key="private-object-key",
                )
            ],
        )
        await connection.execute(
            insert(source_artifacts),
            [
                dict(
                    id="normalized",
                    **common,
                    role="normalized",
                    sha256=sha256(b"retained text").hexdigest(),
                    bytes=len(b"retained text"),
                    object_key="normalized-key",
                )
            ],
        )
        await connection.execute(
            insert(source_versions),
            [
                dict(
                    id=version,
                    **common,
                    artifact_id="artifact",
                    logical_key="logical",
                    operation_id=version,
                    filename=f"{version}.txt",
                    actor="historical-owner",
                    media_type="text/plain",
                )
                for version in ("old", "new")
            ],
        )
        await connection.execute(
            insert(source_extractions),
            [
                dict(
                    id=extraction,
                    **common,
                    version_id=version,
                    purpose="ingestion",
                    normalized_artifact_id="normalized",
                    implementation={"internal": "not public"},
                    coverage="complete",
                    projection={"secret": "omit"},
                )
                for extraction, version in (("old-extraction", "old"), ("new-extraction", "new"))
            ],
        )
        await connection.execute(
            insert(source_parts),
            [
                dict(
                    id="part",
                    **common,
                    extraction_id="old-extraction",
                    kind="chunk",
                    ordinal=1,
                    artifact_id="normalized",
                    text="retained text",
                    sha256=sha256(b"retained text").hexdigest(),
                    page=7,
                    projection_chunk_id="not-public",
                    offset_basis="recorded_loader",
                )
            ],
        )
        await connection.execute(
            insert(source_events),
            [
                dict(
                    id="committed-event",
                    **common,
                    version_id="old",
                    extraction_id="old-extraction",
                    status="committed",
                )
            ],
        )
    statements = []
    event.listen(
        engine.sync_engine,
        "before_cursor_execute",
        lambda connection, cursor, statement, parameters, context, executemany: statements.append(statement),
    )
    adapter = NativeDocumentHistory(DocumentHistoryRepository(DocumentHistoryResources(lambda: lineage)))
    adapter.test_engine = engine
    adapter.test_objects = objects
    adapter.test_statements = statements
    try:
        yield adapter, dict(tenant_id="tenant", workspace_id="workspace", source_id="source", actor="reader")
    finally:
        await engine.dispose()


async def test_version_and_part_pages_keep_exact_historical_identity_without_text_or_storage(history):
    adapter, scope = history
    versions = await adapter.versions(**scope, page=2, page_size=1)
    assert versions["total"] == 2 and len(versions["items"]) == 1
    version = await adapter.version(**scope, source_version_id="old")
    assert version["filename"] == "old.txt" and version["actor"] == "historical-owner"
    assert version["sha256"] == sha256(b"historical original").hexdigest()
    page = await adapter.parts(**scope, source_version_id="old", extraction_id="old-extraction", kind="chunk")
    assert page["items"][0]["recorded_page"] == 7
    part_queries = [query for query in adapter.test_statements if "FROM canon_source_parts" in query]
    assert part_queries and all("canon_source_parts.text" not in query for query in part_queries)
    assert (
        not {"text", "projection_chunk_id", "object_key", "projection", "implementation"}
        & page["items"][0].keys()
    )
    original = await adapter.original(**scope, source_version_id="old", max_bytes=1024)
    assert original.content == b"historical original" and original.filename == "old.txt"


@pytest.mark.parametrize("operation", ["extractions", "parts", "part"])
async def test_missing_version_and_wrong_version_extraction_fail_closed(history, operation):
    adapter, scope = history
    args = {**scope, "source_version_id": "missing"}
    if operation != "extractions":
        args["extraction_id"] = "old-extraction"
    if operation == "part":
        args["source_part_id"] = "part"
    with pytest.raises(ResourceNotFoundException):
        await getattr(adapter, operation)(**args)
    if operation != "extractions":
        args["source_version_id"] = "new"
        with pytest.raises(ResourceNotFoundException):
            await getattr(adapter, operation)(**args)


async def test_cross_workspace_and_pagination_bounds(history):
    adapter, scope = history
    with pytest.raises(ResourceNotFoundException):
        await adapter.version(**{**scope, "workspace_id": "foreign"}, source_version_id="old")
    for args in ({"page": 0}, {"page": 100002}, {"page_size": 0}, {"page_size": 101}, {"page_size": True}):
        with pytest.raises(InvalidRequestException):
            await adapter.versions(**scope, **args)


async def test_public_service_rechecks_binding_before_returning_retained_content():
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.document_history.service import DocumentHistoryService

    changed = False
    calls = []

    async def document(subject, tenant, document_id):
        calls.append(subject)
        return [SimpleNamespace(id=document_id), SimpleNamespace(id="catalog-source")], SimpleNamespace(
            native_id="changed" if changed else "source",
            native_workspace_id="workspace",
        )

    async def version(**scope):
        nonlocal changed
        changed = True
        return dict(
            source_version_id="version",
            filename="old.txt",
            media_type="text/plain",
            sha256="a" * 64,
            byte_size=1,
            actor="owner",
            created_at=datetime.now(UTC),
            predecessor_source_version_id=None,
        )

    service = DocumentHistoryService(
        SimpleNamespace(authorize_document_read=document), SimpleNamespace(version=version)
    )
    with pytest.raises(AccessDenied):
        await service.version("reader", "tenant", "document", "version")
    assert calls == ["reader", "reader"]


async def test_exact_ingestion_part_uses_verified_retained_bytes_and_rejects_corruption(history):
    from pyfly.kernel import ServiceUnavailableException

    adapter, scope = history
    part = await adapter.part(
        **scope, source_version_id="old", extraction_id="old-extraction", source_part_id="part"
    )
    assert part["text"] == "retained text" and part["kind"] == "chunk"
    assert part["sha256"] == sha256(part["text"].encode()).hexdigest()
    assert part["raw_sha256"] == sha256(b"historical original").hexdigest()
    adapter.test_objects["private-object-key"] = b"corrupt"
    with pytest.raises(ServiceUnavailableException):
        await adapter.part(
            **scope, source_version_id="old", extraction_id="old-extraction", source_part_id="part"
        )


async def test_exact_part_rejects_content_above_utf8_boundary(history):
    from flycanon.models.entities.source_lineage import source_parts
    from pyfly.kernel import PayloadTooLargeException

    adapter, scope = history
    text = "\N{SNOWMAN}" * 350_000
    async with adapter.test_engine.begin() as connection:
        await connection.execute(
            update(source_parts)
            .where(source_parts.c.id == "part")
            .values(
                text=text,
                sha256=sha256(text.encode()).hexdigest(),
            )
        )
    with pytest.raises(PayloadTooLargeException):
        await adapter.part(
            **scope, source_version_id="old", extraction_id="old-extraction", source_part_id="part"
        )
