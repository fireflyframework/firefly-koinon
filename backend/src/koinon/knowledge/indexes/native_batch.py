# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Separate provider execution from short, guarded native publication units."""

from contextlib import asynccontextmanager
from uuid import UUID

from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import text

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.indexes.ann import ann_qualified
from koinon.knowledge.indexes.locks import lock_key
from koinon.knowledge.indexes.transactions import require_detached_provider_work


async def validate_target(session, record):
    native = "canon" if record.domain == "documents" else "structured"
    await session.execute(
        text("SELECT pg_advisory_xact_lock_shared(hashtextextended(:key,0))"),
        {"key": lock_key(native, record.tenant_id, record.native_workspace_id)},
    )
    table = "canon_embedding_sets" if native == "canon" else "flyquery_embedding_sets"
    current = (
        (
            await session.execute(
                text(
                    "SELECT provider,model,dimensions,config_fingerprint,status FROM "
                    + table
                    + " WHERE tenant_id=:tenant AND workspace_id=:workspace AND id=:identifier FOR SHARE"
                ),
                {
                    "tenant": record.tenant_id,
                    "workspace": record.native_workspace_id
                    if native == "canon"
                    else UUID(record.native_workspace_id),
                    "identifier": record.native_id,
                },
            )
        )
        .mappings()
        .one_or_none()
    )
    fingerprint = record.cursor.get("native_config_fingerprint")
    if (
        current is None
        or not fingerprint
        or (current["provider"], current["model"], current["dimensions"], current["config_fingerprint"])
        != (record.provider_kind, record.model_id, record.dimensions, fingerprint)
        or current["status"] not in {"queued", "building", "awaiting_index", "ready"}
    ):
        raise ConflictException(
            "The native index target changed; review this preserved build", code="INDEX_NATIVE_TARGET_CHANGED"
        )


async def step(adapter, record, *, embedder, validate_write, publication_guard):
    require_detached_provider_work()
    domain = record.domain
    with native_scope(
        "canon" if domain == "documents" else "structured",
        record.tenant_id,
        record.native_workspace_id,
        record.updated_by,
    ):
        if domain == "documents":
            from flycanon.core.services.retrieval.corpus_factory import CorpusContext

            corpus = adapter.domains._resolve(CorpusContext)
            if corpus.backend != "pgvector":
                raise ServiceUnavailableException(
                    "Versioned document index management requires the native pgvector backend",
                    code="KNOWLEDGE_INDEX_BACKEND_UNSUPPORTED",
                )
            await corpus.initialise()

        @asynccontextmanager
        async def publish():
            async with publication_guard():
                await validate_write()
                async with infrastructure_unit(adapter.source(domain)) as session:
                    await validate_target(session, record)
                    yield session

        async with publish():
            await adapter.set_state(record, "building")
        if domain == "documents":
            from flycanon.config import CanonSettings
            from flycanon.core.services.embeddings.embedding_service import EmbeddingRegistry
            from flycanon.core.services.embeddings.embedding_sets import (
                EmbeddingSetBinding,
                EmbeddingSetService,
            )
            from flycanon.core.services.embeddings.reindex_service import ReindexService
            from flycanon.core.services.retrieval.corpus_factory import CorpusContext
            from flycanon.models.repositories import ChunkRepository, IngestJobRepository

            domains = adapter.domains
            corpus = domains._resolve(CorpusContext)
            chunks = domains._resolve(ChunkRepository)
            binding = EmbeddingSetBinding(
                record.native_id, record.provider_kind, record.model_id, record.dimensions
            )
            service = ReindexService(
                chunks=chunks,
                jobs=domains._resolve(IngestJobRepository),
                sets=domains._resolve(EmbeddingSetService),
                registry=domains._resolve(EmbeddingRegistry),
                vector_store=corpus.vector_store,
                dense_backend=corpus.dense_backend,
                settings=domains._resolve(CanonSettings),
            )
            result = await service.step(
                tenant_id=record.tenant_id,
                workspace_id=record.native_workspace_id,
                binding=binding,
                batch_size=record.batch_size,
                validate_write=validate_write,
                publication_guard=publish,
            )
            result.update(
                await chunks.coverage_counts(
                    tenant_id=record.tenant_id,
                    workspace_id=record.native_workspace_id,
                    set_id=record.native_id,
                )
            )
            indexed = False
        else:
            from flyquery.core.services.retrieval.versioned_index import VersionedIndexService
            from flyquery.models.repositories.embedding_set_repository import EmbeddingSetRepository

            repository = EmbeddingSetRepository(adapter.source(domain).sessionmaker)
            result = await VersionedIndexService(repository).step(
                tenant_id=record.tenant_id,
                workspace_id=record.native_workspace_id,
                set_id=record.native_id,
                embedder=embedder,
                dimensions=record.dimensions,
                model=record.model_id,
                batch_size=record.batch_size,
                validate_write=validate_write,
                publication_guard=publish,
            )
            async with infrastructure_unit(adapter.source(domain)) as session:
                indexed = await ann_qualified(
                    session, domain=domain, set_id=record.native_id, dimensions=record.dimensions
                )
        if result["complete"]:
            async with publication_guard():
                await validate_write()
                # Native batch commits before owner-side DDL obtains its table lock.
                if domain == "documents":
                    indexed = await adapter.provision_document(record)
                async with infrastructure_unit(adapter.source(domain)) as session:
                    await validate_target(session, record)
                    result.update(await adapter.coverage(record))
                    await adapter.set_state(
                        record,
                        "ready"
                        if result["complete"] and indexed
                        else "awaiting_index"
                        if result["complete"]
                        else "building",
                    )
        return {**result, "indexed": indexed}
