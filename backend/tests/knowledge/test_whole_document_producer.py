# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Compose the committed native producer with the actual guarded product receiver."""

import asyncio
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from flycanon.config import CanonSettings
from flycanon.core.services.ingestion.chunker import ParagraphChunker
from flycanon.core.services.ingestion.ingestion_service import IngestionService
from flycanon.core.services.ingestion.loaders import default_registry
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.corpus import CanonCorpusBuilder
from flycanon.core.services.query.rlm.page_cache import MemoryPageCache
from flycanon.core.services.sources.intake_service import IntakeService
from flycanon.core.services.storage.local_fs import LocalFsObjectStore
from flycanon.interfaces.dtos.source import SubmitSourceRequest
from flycanon.models.entities import Base
from flycanon.models.entities.source_lineage import metadata, source_extractions
from flycanon.models.repositories import ChunkRepository, SourceRepository
from pyfly.agentic.content.binary import BinaryArtifact
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from koinon.knowledge.capture_receipt import NativeEvidenceReceipt


async def test_whole_document_commit_precedes_real_receiver_and_model_context(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'whole-read.db'}")
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.run_sync(metadata.create_all)
            await connection.execute(text("DROP INDEX uq_canon_sources_tenant_workspace_content_sha256"))
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        sources, chunks = SourceRepository(sessions), ChunkRepository(sessions)
        objects = LocalFsObjectStore(str(tmp_path / "objects"))
        registry = default_registry()
        intake = IntakeService(
            binary_normalizer=SimpleNamespace(
                normalise=AsyncMock(
                    return_value=[
                        BinaryArtifact(
                            bytes=b"Exact normalized context",
                            kind="text",
                            media_type="text/plain",
                            filename="one.txt",
                        )
                    ]
                )
            ),
            ingestion=IngestionService(loaders=registry, chunker=ParagraphChunker()),
            loaders=registry,
            embeddings=SimpleNamespace(model="controlled-no-network", embed=AsyncMock(return_value=[[1.0]])),
            indexer=SimpleNamespace(replace_for_source=AsyncMock(return_value=1)),
            metadata_extractor=SimpleNamespace(
                extract=Mock(return_value=SimpleNamespace(to_dict=lambda: {}))
            ),
            source_repository=sources,
            chunk_repository=chunks,
            audit=SimpleNamespace(record=AsyncMock()),
            event_publisher=None,
            object_store=objects,
            settings=CanonSettings(store_originals=True, pii_policy="disabled"),
        )
        source = await intake.submit(
            request=SubmitSourceRequest(),
            content=b"Different raw original",
            tenant_id="tenant",
            workspace_id="workspace",
            actor="owner",
            filename="one.txt",
            logical_source_key="logical-document",
            operation_id="upload",
        )
        receipt = NativeEvidenceReceipt("owner", "tenant")
        receipt.authorize_model = AsyncMock(return_value=True)
        receipt.admit_documents(
            "tenant",
            "workspace",
            "owner",
            {
                source.id: (
                    SimpleNamespace(id="asset", workspace_id="canonical", name="Controlled"),
                    SimpleNamespace(id="source-parent"),
                )
            },
        )
        recorded = receipt.document_extraction
        loop = asyncio.get_running_loop()

        async def committed(identifier):
            async with sessions() as session:
                return (
                    await session.execute(
                        select(source_extractions.c.purpose).where(source_extractions.c.id == identifier)
                    )
                ).scalar_one()

        def observe(source_id, version_id, extraction_id, scope):
            assert (
                asyncio.run_coroutine_threadsafe(committed(extraction_id), loop).result(timeout=5)
                == "whole_document_read"
            )
            recorded(source_id, version_id, extraction_id, scope)

        receipt.document_extraction = observe
        stale_pages = MemoryPageCache(ttl_s=60, max_entries=8)
        stale_pages.set(source.content_sha256, ["Foreign cached text"])
        stale_pages.set(sha256(b"Different raw original").hexdigest(), ["Unverified cached original"])
        with provenance.observe(
            receipt, tenant_id="tenant", workspace_id="workspace", actor="owner", source_ids={source.id}
        ):
            docs = await CanonCorpusBuilder(
                source_repository=sources,
                knowledge_repository=None,
                object_store=objects,
                registry=registry,
                cache=stale_pages,
            ).build(tenant_id="tenant", workspace_id="workspace")
            await provenance.corpus(docs)
            assert receipt.native_reads[-1].read_kind == "metadata"
            assert receipt.native_reads[-1].source_version_id is None

            @provenance.worker
            def consume():
                content = docs[docs.keys()[0]]
                provenance.model("rlm.root", content)
                return content

            actual = await asyncio.to_thread(consume)
        assert actual == "Exact normalized context"
        assert len(receipt.documents) == 1
        part = next(iter(receipt.documents.values()))
        assert part.quote == actual and part.digest == sha256(actual.encode()).hexdigest()
        assert part.source_part_sha256 == sha256(actual.encode()).hexdigest()
        assert len(receipt.document_extractions) == 1
        metadata_read, document_read, model_input = receipt.native_reads
        assert metadata_read.extraction_id is None
        assert document_read.stage == "rlm.read" and model_input.stage == "rlm.root"
        assert document_read.read_kind == model_input.read_kind == "document_extraction"
        assert (
            document_read.source_version_id
            == model_input.source_version_id
            == source.metadata_json["_source_lineage"]["version_id"]
        )
        assert document_read.extraction_id == model_input.extraction_id
        assert document_read.content_sha256 == sha256(actual.encode()).hexdigest()
    finally:
        await engine.dispose()
