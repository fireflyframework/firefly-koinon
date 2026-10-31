# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Source intake orchestrator -- bytes in, indexed source out.

End-to-end pipeline that controllers + workers call when ingesting a
new binary. The orchestrator owns:

1. **Binary normalisation** -- :class:`BinaryNormalizer` sniffs the
   actual media type from magic bytes, routes through the right
   adapter (image conversion, archive expansion, email
   decomposition, optional Office conversion), and emits one or more
   :class:`BinaryArtifact` rows.

2. **Loading** -- each artifact is fed to the loader registered for
   its kind, producing a :class:`LoadedDocument` with heading-anchored
   sections. Multi-artifact intakes (archives, emails) are merged
   into a single document with constituent section markers so the
   retrieval index sees one logical source per intake call.

3. **Chunking** -- :class:`ParagraphChunker` packs paragraphs into
   token-budgeted chunks with soft overlap.

4. **Embedding** -- :class:`EmbeddingService` produces one vector
   per chunk in batched, retried, cost-tracked calls.

5. **Indexing** -- :class:`IndexService` writes the BM25 + dense
   projections to the corpus + vector store, keyed by ``chunk_id``
   so retrieval-time RRF fusion lines up.

6. **Audit + EDA** -- :class:`AuditService` records the mutation and
   the event publisher broadcasts ``SourceIngested`` on
   ``flycanon.ingest``.
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
import mimetypes
import os
import uuid
from typing import Any

from pyfly.agentic.content.binary import BinaryNormalizer
from pyfly.container import service
from pyfly.eda import EventPublisher
from pyfly.kernel import DuplicateKeyException
from sqlalchemy.exc import IntegrityError

from flycanon.config import CanonSettings
from flycanon.core.mappers.intake_mapper import _ancestry_metadata as _ancestry_metadata
from flycanon.core.mappers.intake_mapper import _metadata_to_json as _metadata_to_json
from flycanon.core.mappers.intake_mapper import _render_document as _render_document
from flycanon.core.services.audit import AuditService
from flycanon.core.services.embeddings import (
    EmbeddingRegistry,
    EmbeddingService,
    EmbeddingSetService,
    bind_embedding_set,
)
from flycanon.core.services.ingestion import IngestionService
from flycanon.core.services.ingestion.loaders import LoaderRegistry
from flycanon.core.services.metadata import MetadataExtractor
from flycanon.core.services.retrieval import IndexService
from flycanon.core.services.sources.errors import SourceNotFound
from flycanon.core.services.sources.intake_events import publish_failure, publish_success
from flycanon.core.services.sources.intake_policy import SourceIntakePolicy, build_intake_policy
from flycanon.core.services.sources.intake_transforms import (
    apply_pii_policy,
    decode_for_scan,
    embedder_for,
    first_text,
    merge_artifacts,
)
from flycanon.core.services.sources.lineage.pipeline import DocumentLineagePipeline
from flycanon.core.services.sources.lineage.ports import PublicationGuard, StageAuthorization
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.interfaces.dtos.intake import SourceRemoval as SourceRemoval
from flycanon.interfaces.dtos.source import SubmitSourceRequest
from flycanon.interfaces.enums import SourceKind, SourceStatus
from flycanon.models.entities.source import SourceRow
from flycanon.models.repositories.chunk_repository import ChunkRepository
from flycanon.models.repositories.source_repository import SourceRepository

logger = logging.getLogger(__name__)


@service(name="canon.IntakeService")
class IntakeService:
    """End-to-end source intake: normalise -> load -> chunk -> embed -> index."""

    def __init__(
        self,
        binary_normalizer: BinaryNormalizer,
        ingestion: IngestionService,
        loaders: LoaderRegistry,
        embeddings: EmbeddingService,
        indexer: IndexService,
        metadata_extractor: MetadataExtractor,
        source_repository: SourceRepository,
        chunk_repository: ChunkRepository,
        audit: AuditService,
        event_publisher: EventPublisher,
        object_store: ObjectStore,
        settings: CanonSettings,
        embedding_sets: EmbeddingSetService | None = None,
        embedding_registry: EmbeddingRegistry | None = None,
        lineage_pipeline: DocumentLineagePipeline | None = None,
        intake_policy: SourceIntakePolicy | None = None,
    ) -> None:
        self._lineage_pipeline = lineage_pipeline
        self._binary_normalizer = binary_normalizer
        self._ingestion = ingestion
        self._loaders = loaders
        self._embeddings = embeddings
        self._indexer = indexer
        self._metadata = metadata_extractor
        self._sources = source_repository
        self._chunks = chunk_repository
        self._audit = audit
        self._publisher = event_publisher
        self._object_store = object_store
        self._settings = settings
        # Which embedding space this workspace's vectors go into, and the
        # embedder that produces them. Optional so a test that wires a mock
        # embedder and a mock index keeps the pre-26.8.0 shape.
        self._embedding_sets = embedding_sets
        self._embedding_registry = embedding_registry
        policy = intake_policy or build_intake_policy(settings)
        self._pii_policy = policy.value
        self._pii_scanner = policy.scanner

    async def _embedder_for(self, *, tenant_id: str, workspace_id: str):
        return await embedder_for(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            embeddings=self._embeddings,
            embedding_sets=self._embedding_sets,
            embedding_registry=self._embedding_registry,
        )

    async def submit(
        self,
        *,
        request: SubmitSourceRequest,
        content: bytes,
        tenant_id: str,
        workspace_id: str,
        filename: str | None = None,
        content_type: str | None = None,
        actor: str | None = None,
        correlation_id: str | None = None,
        logical_source_key: str | None = None,
        operation_id: str | None = None,
        authorize_commit=None,
        publication_guard: PublicationGuard | None = None,
        validate_processing: StageAuthorization | None = None,
        validate_publication: StageAuthorization | None = None,
    ) -> SourceRow:
        """Run the full intake pipeline and return the populated row."""
        if logical_source_key is not None:
            if self._lineage_pipeline is None:
                raise RuntimeError("Provide the managed DocumentLineagePipeline for versioned source intake")
            return await self._lineage_pipeline.run(
                request=request,
                content=content,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                actor=actor,
                filename=filename,
                content_type=content_type,
                logical_key=logical_source_key,
                operation_id=operation_id or logical_source_key,
                authorize_commit=authorize_commit,
                correlation_id=correlation_id,
                publication_guard=publication_guard,
                validate_processing=validate_processing,
                validate_publication=validate_publication,
            )
        artifacts = await self._binary_normalizer.normalise(
            content,
            declared_media_type=content_type,
            filename=filename,
        )
        merged_kind, merged_content, merged_metadata = self._merge_artifacts(artifacts, filename)
        merged_content, merged_metadata = self._apply_pii_policy(merged_content, merged_metadata)

        primary_kind = request.kind if request.kind != SourceKind.unknown else merged_kind

        source = SourceRow(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            kind=primary_kind.value,
            status=SourceStatus.pending.value,
            filename=filename,
            uri=request.uri,
            content_type=content_type,
            content_sha256="",
            content_bytes=0,
            metadata_json={**_metadata_to_json(request.metadata), **merged_metadata},
        )

        try:
            result = self._ingestion.ingest(
                source=source,
                content=merged_content,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )
        except Exception as exc:
            source.status = SourceStatus.failed.value
            source.error_code = getattr(exc, "code", "ingestion_failed")
            source.error_message = str(exc)
            await self._sources.add(source)
            await self._publish_failure(source=source, exc=exc, correlation_id=correlation_id)
            raise

        # Per-format metadata extraction. We feed the loader-produced
        # text back into the language detector so the ``language``
        # field is populated even when the embedded metadata doesn't
        # carry one. The extracted dict lands under
        # ``metadata_json.extracted`` so the source schema stays
        # stable while still exposing the rich facets.
        primary_artifact = artifacts[0] if artifacts else None
        primary_media = primary_artifact.media_type if primary_artifact else (content_type or "")
        primary_bytes = primary_artifact.bytes if primary_artifact else merged_content
        text_sample = self._first_text(result.chunks)
        extracted = self._metadata.extract(
            primary_bytes,
            media_type=primary_media,
            filename=filename,
            text_sample=text_sample,
        )
        metadata = dict(result.source.metadata_json or {})
        metadata["extracted"] = extracted.to_dict()
        result.source.metadata_json = metadata

        # Idempotent on the SHA-256: the same bytes resolve to the
        # same row, no matter how many parallel callers submit them.
        # We pre-check + handle IntegrityError so the race window
        # between the SELECT and the INSERT is also covered (without
        # the recovery branch, the second caller would see a 500
        # IntegrityError from the partial-unique index on
        # ``content_sha256``).
        existing = await self._sources.get_by_content_sha256(
            result.source.content_sha256,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        if existing is not None:
            logger.info(
                "intake idempotent: content_sha256=%s already mapped to source_id=%s",
                result.source.content_sha256,
                existing.id,
            )
            return existing

        # Persist the ORIGINAL uploaded bytes (not merged_content) so RLM
        # can re-extract whole-document text from the canonical file via
        # the loaders. Best-effort: a storage failure logs a warning and
        # leaves ``object_store_key`` null rather than failing the ingest.
        # Setting the key before the INSERT lands it on the same row.
        if self._settings.store_originals:
            await self._store_original(
                source=result.source,
                content=content,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                filename=filename,
                content_type=content_type,
            )

        try:
            await self._sources.add(result.source)
        except (IntegrityError, DuplicateKeyException):
            existing = await self._sources.get_by_content_sha256(
                result.source.content_sha256,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )
            if existing is not None:
                logger.info(
                    "intake idempotent (race-resolved): content_sha256=%s -> source_id=%s",
                    result.source.content_sha256,
                    existing.id,
                )
                return existing
            raise

        if result.chunks:
            binding, embedder = await self._embedder_for(tenant_id=tenant_id, workspace_id=workspace_id)
            texts = [chunk.content for chunk in result.chunks]
            with bind_embedding_set(binding) if binding is not None else contextlib.nullcontext():
                embeddings = await embedder.embed(texts)
                # Stamp the model on the chunks BEFORE persisting so the
                # canon_chunks row carries the right ``embedding_model``
                # column on its single INSERT. The vector projection then
                # mirrors the same chunk ids into the chosen vector store
                # for retrieval-time RRF fusion.
                for chunk in result.chunks:
                    chunk.embedding_model = embedder.model
                await self._chunks.replace_for_source(result.source.id, result.chunks)
                await self._indexer.replace_for_source(
                    source=result.source,
                    chunks=result.chunks,
                    embeddings=embeddings,
                    embedding_model=embedder.model,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                )
        else:
            await self._chunks.replace_for_source(result.source.id, [])

        await self._audit.record(
            event_type="source.ingested",
            subject_kind="source",
            subject_id=result.source.id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            actor=actor,
            correlation_id=correlation_id,
            payload={
                "kind": result.source.kind,
                "content_sha256": result.source.content_sha256,
                "n_chunks": result.source.n_chunks,
                "n_artifacts": len(artifacts),
            },
        )
        await self._publish_success(source=result.source, correlation_id=correlation_id)
        logger.info(
            "intake completed id=%s kind=%s n_chunks=%d n_artifacts=%d",
            result.source.id,
            result.source.kind,
            result.source.n_chunks,
            len(artifacts),
        )
        return result.source

    async def replace(
        self,
        *,
        source_id: str,
        request: SubmitSourceRequest,
        content: bytes,
        tenant_id: str,
        workspace_id: str,
        filename: str | None = None,
        content_type: str | None = None,
        actor: str | None = None,
        correlation_id: str | None = None,
        versioned_originals: bool = False,
        logical_source_key: str | None = None,
        operation_id: str | None = None,
        expected_source_version_id: str | None = None,
        expected_extraction_id: str | None = None,
        authorize_commit=None,
    ) -> SourceRow:
        """Re-ingest an existing source in place, preserving the row id.

        Use when a canonical file is updated and downstream citations
        should follow the new content rather than orphan to the deleted
        row. The flow:

        1. Look up the existing :class:`SourceRow` -- 404 propagates
           up if it's missing.
        2. Normalise + load + chunk + embed the new bytes through the
           same pipeline as :meth:`submit`.
        3. Drop the existing chunks + their vector projection via
           :meth:`ChunkRepository.replace_for_source` /
           :meth:`IndexService.replace_for_source` (idempotent --
           same calls the submit path makes).
        4. UPDATE the existing source row's mutable fields
           (filename, uri, content_sha256, content_bytes, n_chunks,
           metadata_json) instead of inserting a new row.
        5. Audit ``source.replaced`` + publish a ``SourceReplaced``
           EDA event so downstream projections can re-sync.

        Citations referencing chunks that disappear in the new
        emission are not deleted -- a future pass surfaces them as
        ``dangling_citation`` audit warnings. v1 simply preserves
        the citation rows (their ``chunk_id`` will resolve to
        ``None`` in the provenance graph; out of scope for this
        commit to repair).
        """
        if logical_source_key is not None:
            if self._lineage_pipeline is None:
                raise RuntimeError("Provide the managed DocumentLineagePipeline for versioned source intake")
            return await self._lineage_pipeline.run(
                request=request,
                content=content,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                actor=actor,
                filename=filename,
                content_type=content_type,
                logical_key=logical_source_key,
                operation_id=operation_id or str(uuid.uuid4()),
                source_id=source_id,
                expected_source_version_id=expected_source_version_id,
                expected_extraction_id=expected_extraction_id,
                authorize_commit=authorize_commit,
                correlation_id=correlation_id,
            )
        existing = await self._sources.get(
            source_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        if existing is None:
            raise SourceNotFound(source_id)

        artifacts = await self._binary_normalizer.normalise(
            content,
            declared_media_type=content_type,
            filename=filename,
        )
        merged_kind, merged_content, merged_metadata = self._merge_artifacts(artifacts, filename)
        # PII guardrail runs on the re-ingest path too: a clean v1 of
        # a file may be replaced with a v2 that introduces emails /
        # SSNs / etc., and the policy must catch that just like
        # initial submit. Same scanner + policy resolution as submit().
        merged_content, merged_metadata = self._apply_pii_policy(merged_content, merged_metadata)
        primary_kind = request.kind if request.kind != SourceKind.unknown else merged_kind

        # Build a transient SourceRow carrying the NEW values so the
        # ingestion pipeline (which already knows how to chunk +
        # compute content_sha256 + emit chunks for a row) does its
        # work; we then transplant the result onto the EXISTING row
        # (preserving its id + created_at + audit history).
        scratch = SourceRow(
            id=existing.id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            kind=primary_kind.value,
            status=SourceStatus.pending.value,
            filename=filename or existing.filename,
            uri=request.uri or existing.uri,
            content_type=content_type or existing.content_type,
            content_sha256="",
            content_bytes=0,
            metadata_json={
                **(existing.metadata_json or {}),
                **_metadata_to_json(request.metadata),
                **merged_metadata,
            },
        )
        result = self._ingestion.ingest(
            source=scratch,
            content=merged_content,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )

        # Per-format metadata extraction (identical to submit()).
        primary_artifact = artifacts[0] if artifacts else None
        primary_media = primary_artifact.media_type if primary_artifact else (content_type or "")
        primary_bytes = primary_artifact.bytes if primary_artifact else merged_content
        text_sample = self._first_text(result.chunks)
        extracted = self._metadata.extract(
            primary_bytes,
            media_type=primary_media,
            filename=filename,
            text_sample=text_sample,
        )
        metadata = dict(result.source.metadata_json or {})
        metadata["extracted"] = extracted.to_dict()

        # Now flip the existing row in place with the new content
        # (preserves id, created_at, ingested_at history).
        existing.kind = result.source.kind
        existing.status = SourceStatus.ingested.value
        existing.filename = scratch.filename
        existing.uri = scratch.uri
        existing.content_type = scratch.content_type
        existing.content_sha256 = result.source.content_sha256
        existing.content_bytes = result.source.content_bytes
        existing.n_chunks = result.source.n_chunks
        existing.metadata_json = metadata
        existing.error_code = None
        existing.error_message = None

        if versioned_originals:
            existing.object_store_key = None
            existing.metadata_json = {
                key: value for key, value in existing.metadata_json.items() if key != "_persisted_original"
            }

        # Persist the NEW original bytes on the re-ingest path too, so the
        # stored corpus follows the replaced content. Best-effort: a write
        # failure leaves the key as-is and never fails the replace.
        if self._settings.store_originals:
            await self._store_original(
                source=existing,
                content=content,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                filename=existing.filename,
                content_type=existing.content_type,
                versioned=versioned_originals,
            )

        updated_row = await self._sources.update(existing)

        if result.chunks:
            binding, embedder = await self._embedder_for(tenant_id=tenant_id, workspace_id=workspace_id)
            texts = [chunk.content for chunk in result.chunks]
            with bind_embedding_set(binding) if binding is not None else contextlib.nullcontext():
                embeddings = await embedder.embed(texts)
                for chunk in result.chunks:
                    chunk.embedding_model = embedder.model
                    chunk.source_id = updated_row.id
                await self._chunks.replace_for_source(updated_row.id, result.chunks)
                await self._indexer.replace_for_source(
                    source=updated_row,
                    chunks=result.chunks,
                    embeddings=embeddings,
                    embedding_model=embedder.model,
                    tenant_id=tenant_id,
                    workspace_id=workspace_id,
                )
        else:
            await self._chunks.replace_for_source(updated_row.id, [])

        await self._audit.record(
            event_type="source.replaced",
            subject_kind="source",
            subject_id=updated_row.id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            actor=actor,
            correlation_id=correlation_id,
            payload={
                "kind": updated_row.kind,
                "content_sha256": updated_row.content_sha256,
                "n_chunks": updated_row.n_chunks,
                "n_artifacts": len(artifacts),
            },
        )
        if self._publisher is not None:
            try:
                await self._publisher.publish(  # type: ignore[attr-defined]
                    destination=self._settings.ingest_topic,
                    event_type="SourceReplaced",
                    payload={
                        "source_id": updated_row.id,
                        "tenant_id": tenant_id,
                        "workspace_id": workspace_id,
                        "kind": updated_row.kind,
                        "content_sha256": updated_row.content_sha256,
                        "n_chunks": updated_row.n_chunks,
                    },
                    headers={"correlation-id": correlation_id} if correlation_id else None,
                )
            except Exception as exc:
                logger.warning(
                    "SourceReplaced publish failed source_id=%s: %s",
                    updated_row.id,
                    exc,
                )
        logger.info(
            "intake replaced id=%s kind=%s n_chunks=%d",
            updated_row.id,
            updated_row.kind,
            updated_row.n_chunks,
        )
        return updated_row

    async def remove(
        self,
        *,
        source_id: str,
        tenant_id: str,
        workspace_id: str,
        actor: str | None = None,
        correlation_id: str | None = None,
    ) -> SourceRemoval:
        """Remove a source and every indexed projection for it.

        Returns a :class:`SourceRemoval` stating whether a stored
        original was actually deleted, so callers that aggregate
        (the workspace purge) report the same fact the audit row does.

        The flow:

        1. Look up the existing :class:`SourceRow` scoped to
           ``(tenant_id, workspace_id)`` -- raises
           :class:`SourceNotFound` (404) when the id is unknown.
        2. Purge the index projections via
           :meth:`IndexService.remove_for_source` (BM25 rows + dense
           vectors). This runs BEFORE the chunk rows are deleted --
           the indexer resolves the source's chunk ids through the
           chunk repository, so deleting the rows first would leak
           the dense vectors.
        3. Delete the chunk rows
           (:meth:`ChunkRepository.replace_for_source` with an empty
           set) and then the source row itself.
        4. Delete the stored original from the object store when the
           row carries an ``object_store_key``. Until 26.7.1 removal
           left the bytes behind, which for a tenant's off-boarding or
           a retention delete meant the document the caller asked to
           erase stayed readable by the RLM answer path (it reads
           originals, not chunks) and stayed on disk / in the bucket.
           The delete is attempted BEFORE the row goes so a failure
           leaves a row that still points at the object and can be
           retried, rather than an orphaned object nobody references.
           A missing object (``FileNotFoundError``) is not an error --
           the store port defines delete as idempotent.
        5. Audit ``source.removed`` + publish a ``SourceRemoved`` EDA
           event so downstream projections can re-sync, mirroring
           ``SourceIngested`` / ``SourceReplaced``.
        """
        existing = await self._sources.get(
            source_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        if existing is None:
            raise SourceNotFound(source_id)

        await self._indexer.remove_for_source(
            source_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
        )
        await self._chunks.replace_for_source(source_id, [])
        original_deleted = await self._delete_original(existing)
        await self._sources.delete(existing)

        await self._audit.record(
            event_type="source.removed",
            subject_kind="source",
            subject_id=source_id,
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            actor=actor,
            correlation_id=correlation_id,
            payload={
                "kind": existing.kind,
                "content_sha256": existing.content_sha256,
                "original_deleted": original_deleted,
            },
        )
        if self._publisher is not None:
            try:
                await self._publisher.publish(  # type: ignore[attr-defined]
                    destination=self._settings.ingest_topic,
                    event_type="SourceRemoved",
                    payload={
                        "source_id": source_id,
                        "tenant_id": tenant_id,
                        "workspace_id": workspace_id,
                        "kind": existing.kind,
                        "content_sha256": existing.content_sha256,
                        "original_deleted": original_deleted,
                    },
                    headers={"correlation-id": correlation_id} if correlation_id else None,
                )
            except Exception as exc:
                logger.warning(
                    "SourceRemoved publish failed source_id=%s: %s",
                    source_id,
                    exc,
                )
        logger.info(
            "intake removed id=%s kind=%s original_deleted=%s",
            source_id,
            existing.kind,
            original_deleted,
        )
        return SourceRemoval(source_id=source_id, original_deleted=original_deleted)

    async def _delete_original(self, source: SourceRow) -> bool:
        """Delete the stored original for ``source``; return whether one was removed.

        ``False`` when the row never had a key (``store_originals`` was
        off at ingest, or the put failed and the ingest continued) or
        when the object is not in the store. Any other store failure
        propagates so the caller's row is left intact and the removal
        can be retried -- see :meth:`remove`.

        The existence check comes first because the :class:`ObjectStore`
        port defines ``delete`` as a no-op on a missing key (localfs
        unlinks with ``missing_ok``, S3's ``DeleteObject`` is silent), so
        ``delete`` alone cannot tell "erased" from "was never here". The
        difference matters: a row whose key is not in this process's
        store means the API and the worker are looking at different
        stores (a localfs root that is not a shared volume, a bucket
        mismatch) and the bytes the caller asked to erase are still
        wherever the worker put them. That is logged as a warning with
        the key, and reported as ``original_deleted=False`` rather than
        claimed as done. The check-then-delete pair is not atomic; a
        concurrent delete of the same key can only turn a ``True`` into
        an over-report of one object that is gone either way.
        """
        key = getattr(source, "object_store_key", None)
        if not key:
            return False
        if not await self._object_store.exists(key):
            logger.warning(
                "intake remove: source %s points at object %r that is not in the object store; "
                "the original was NOT deleted here (is the API's object store the worker's?)",
                source.id,
                key,
            )
            return False
        try:
            await self._object_store.delete(key)
        except FileNotFoundError:
            return False
        return True

    def _apply_pii_policy(self, content: bytes, metadata: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
        return apply_pii_policy(content, metadata, policy=self._pii_policy, scanner=self._pii_scanner)

    async def _store_original(
        self,
        *,
        source: SourceRow,
        content: bytes,
        tenant_id: str,
        workspace_id: str,
        filename: str | None,
        content_type: str | None,
        versioned: bool = False,
    ) -> None:
        """Write the original bytes to the object store and stamp the key.

        Key layout mirrors flyquery's convention:
        ``flycanon/{tenant}/{workspace}/sources/{source_id}{ext}``. The
        extension is taken from the filename when present, else guessed
        from ``content_type``, else ``.bin``. Best-effort: on any failure
        we log a warning and leave ``object_store_key`` unchanged so the
        ingest still succeeds.
        """
        ext = self._original_extension(filename, content_type)
        key = f"flycanon/{tenant_id}/{workspace_id}/sources/{source.id}{ext}"
        if versioned:
            digest = hashlib.sha256(content).hexdigest()
            key = f"flycanon/{tenant_id}/{workspace_id}/sources/{source.id}/{digest}{ext}"
        try:
            await self._object_store.put(key, content, content_type)
        except Exception as exc:
            logger.warning(
                "object-store put failed source_id=%s key=%s: %s",
                source.id,
                key,
                exc,
            )
            return
        source.object_store_key = key
        source.metadata_json = {
            **(source.metadata_json or {}),
            "_persisted_original": {"sha256": hashlib.sha256(content).hexdigest(), "bytes": len(content)},
        }

    @staticmethod
    def _original_extension(filename: str | None, content_type: str | None) -> str:
        """Derive a file extension for the stored original."""
        if filename:
            ext = os.path.splitext(filename)[1]
            if ext:
                return ext
        if content_type:
            guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
            if guessed:
                return guessed
        return ".bin"

    @staticmethod
    def _decode_for_scan(content: bytes) -> str:
        return decode_for_scan(content)

    @staticmethod
    def _first_text(chunks: list[Any]) -> str:
        return first_text(chunks)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _merge_artifacts(self, artifacts, original_filename, observer=None):
        return merge_artifacts(artifacts, original_filename, loaders=self._loaders, observer=observer)

    async def _publish_success(self, *, source: SourceRow, correlation_id: str | None) -> None:
        await publish_success(self._publisher, self._settings, source=source, correlation_id=correlation_id)

    async def _publish_failure(
        self, *, source: SourceRow, exc: BaseException, correlation_id: str | None
    ) -> None:
        await publish_failure(
            self._publisher, self._settings, source=source, exc=exc, correlation_id=correlation_id
        )
