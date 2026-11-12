# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Derived document authority follows immutable ingestion ancestry without loading text."""

from contextlib import asynccontextmanager
from dataclasses import replace

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_source_migration_postgres import source_database as source_database

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_dtos import LocalSourcePin
from koinon.integrations.content_sources.read_native import SourceReadNative

pytestmark = pytest.mark.integration


@pytest.fixture
async def native_extractions(source_database, monkeypatch):
    from flycanon.models.entities.source_lineage import (
        metadata,
        source_artifacts,
        source_extractions,
        source_parts,
        source_versions,
    )

    target, _, engine = source_database
    metadata.create_all(engine)
    scope = {"tenant_id": "reader-tenant", "workspace_id": "space", "source_id": "source"}
    with engine.begin() as connection:
        connection.execute(
            source_artifacts.insert(),
            dict(
                id="normalized",
                **scope,
                role="normalized",
                sha256="a" * 64,
                bytes=10,
                object_key="never-read-content",
            ),
        )
        connection.execute(
            source_versions.insert(),
            dict(
                id="version",
                **scope,
                artifact_id="normalized",
                logical_key="logical",
                operation_id="operation",
            ),
        )
        connection.execute(
            source_extractions.insert(),
            [
                dict(
                    id="ingestion",
                    **scope,
                    version_id="version",
                    purpose="ingestion",
                    normalized_artifact_id="normalized",
                    implementation={},
                    coverage="section",
                    projection={},
                ),
                dict(
                    id="derived",
                    **scope,
                    version_id="version",
                    purpose="whole_document_read",
                    normalized_artifact_id="normalized",
                    implementation={},
                    coverage="file_section",
                    projection={"input_extraction_id": "ingestion"},
                ),
                dict(
                    id="forged",
                    **scope,
                    version_id="version",
                    purpose="whole_document_read",
                    normalized_artifact_id="normalized",
                    implementation={},
                    coverage="file_section",
                    projection={"input_extraction_id": "different"},
                ),
            ],
        )
        connection.execute(
            source_parts.insert(),
            dict(
                id="page",
                **scope,
                extraction_id="derived",
                kind="page",
                ordinal=0,
                text="Must never hydrate this text",
                sha256="b" * 64,
            ),
        )
    async_engine = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    sessions = async_sessionmaker(async_engine)

    @asynccontextmanager
    async def unit(*args, **kwargs):
        async with sessions() as session:
            yield session

    monkeypatch.setattr("koinon.integrations.content_sources.read_native.infrastructure_unit", unit)
    try:
        yield LocalSourcePin("asset", "canon", "space", "source", "version", "derived", "page")
    finally:
        await async_engine.dispose()


async def test_committed_derived_extraction_accepts_only_exact_ingestion_ancestry(native_extractions):
    native = SourceReadNative()
    pin = native_extractions
    await native.document_extraction("reader", "reader-tenant", pin, "ingestion")
    for invalid in (
        replace(pin, extraction_id="forged"),
        replace(pin, native_source_id="other"),
        replace(pin, version_id="other"),
        replace(pin, extraction_id="missing"),
        replace(pin, part_id="another-page"),
    ):
        with pytest.raises(SourceError, match="access_denied"):
            await native.document_extraction("reader", "reader-tenant", invalid, "ingestion")
    with pytest.raises(SourceError, match="access_denied"):
        await native.document_extraction("reader", "other-tenant", pin, "ingestion")


async def test_native_candidates_do_not_hydrate_and_exact_pins_reject_projection_changes(
    native_extractions, source_database, monkeypatch
):
    from flycanon.core.services.retrieval.postgres_corpus import PostgresCorpus
    from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
    from flycanon.models.entities.source import SourceRow
    from flycanon.models.entities.source_lineage import source_heads, source_parts
    from flycanon.models.repositories.chunk_repository import ChunkRepository
    from pyfly.kernel import ServiceUnavailableException
    from sqlalchemy import event, text

    target, _, engine = source_database
    SourceRow.__table__.create(engine)
    KnowledgeChunkRow.__table__.create(engine)
    scope = dict(tenant_id="reader-tenant", workspace_id="space", source_id="source")
    with engine.begin() as connection:
        connection.execute(
            SourceRow.__table__.insert(),
            dict(
                id="source",
                tenant_id="reader-tenant",
                workspace_id="space",
                kind="text",
                status="ready",
                content_sha256="c" * 64,
                filename="Protected title",
            ),
        )
        connection.execute(
            KnowledgeChunkRow.__table__.insert(), dict(id="chunk", **scope, content="Protected knowledge")
        )
        connection.execute(
            source_parts.insert(),
            dict(
                id="chunk-part",
                **scope,
                extraction_id="ingestion",
                kind="chunk",
                ordinal=1,
                text="Protected knowledge",
                sha256="d" * 64,
                projection_chunk_id="chunk",
            ),
        )
        connection.execute(
            source_heads.insert(),
            dict(**scope, logical_key="logical", version_id="version", extraction_id="ingestion"),
        )
        connection.execute(
            text(
                "ALTER TABLE canon_chunks ADD COLUMN tsv tsvector "
                "GENERATED ALWAYS AS (to_tsvector('simple',content)) STORED"
            )
        )
    async_engine = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    sessions = async_sessionmaker(async_engine)
    statements = []
    event.listen(
        async_engine.sync_engine,
        "before_cursor_execute",
        lambda _c, _u, statement, _p, _x, _m: statements.append(statement),
    )

    @asynccontextmanager
    async def unit(*args, **kwargs):
        async with sessions() as session:
            yield session

    monkeypatch.setattr("flycanon.models.repositories.chunk_repository.infrastructure_unit", unit)
    try:
        chunks = ChunkRepository(sessions)
        pins = await chunks.candidate_pins(("chunk",), tenant_id="reader-tenant", workspace_id="space")
        assert len(pins) == 1 and pins[0].source_part_id == "chunk-part"
        assert all("canon_chunks.content" not in statement.split("FROM")[0] for statement in statements)
        assert await chunks.candidate_pins(("chunk",), tenant_id="other-tenant", workspace_id="space") == ()
        corpus = PostgresCorpus(datasource=None)
        monkeypatch.setattr(corpus, "_scoped_connection", unit)
        hits = await corpus.bm25_search(
            "Protected", tenant_id="reader-tenant", workspace_id="space", top_k=5, candidates_only=True
        )
        assert len(hits) == 1 and hits[0].content == "" and hits[0].metadata == {}
        assert (await chunks.get_pinned_chunks(pins, tenant_id="reader-tenant", workspace_id="space"))[
            0
        ].content == "Protected knowledge"
        with engine.begin() as connection:
            connection.execute(source_heads.update().values(extraction_id="forged"))
        with pytest.raises(ServiceUnavailableException, match="changed"):
            await chunks.get_pinned_chunks(pins, tenant_id="reader-tenant", workspace_id="space")
    finally:
        await async_engine.dispose()
