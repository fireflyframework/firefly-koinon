# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Short canonical document intake seam; native lineage owns durable promotion."""

from hashlib import sha256

from pyfly.kernel import ConflictException, ResourceNotFoundException
from sqlalchemy import func, select


async def replace_document(
    domains,
    *,
    tenant_id,
    workspace_id,
    source_id,
    filename,
    content,
    expected_sha256,
    actor,
    logical_source_key,
    operation_id,
    force_reingest=False,
    catalog_workspace_id=None,
    authorize_commit=None,
    expected_source_version_id=None,
    expected_extraction_id=None,
):
    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.interfaces.dtos.source import SubmitSourceRequest
    from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
    from flycanon.models.repositories import SourceRepository

    from koinon.knowledge.adapters import native_scope

    with native_scope("canon", tenant_id, workspace_id, actor):
        sources = domains._resolve(SourceRepository)
        source = await sources.get(source_id, tenant_id=tenant_id, workspace_id=workspace_id)
        if source is None:
            raise ResourceNotFoundException(
                "The persisted document is unavailable", code="DOCUMENT_NOT_FOUND"
            )
        lineage = domains._resolve(DocumentLineage)
        head = await lineage.head(DocumentScope(tenant_id, workspace_id, actor), source_id)
        if (
            head is not None
            and head["version_id"] is not None
            and (expected_source_version_id is None or expected_extraction_id is None)
        ):
            raise ConflictException(
                "Review the exact current source version and extraction first",
                code="DOCUMENT_VERSION_REQUIRED",
            )
        if (expected_source_version_id is not None or expected_extraction_id is not None) and (
            head is None
            or (head["version_id"], head["extraction_id"])
            != (expected_source_version_id, expected_extraction_id)
        ):
            raise ConflictException(
                "Document extraction changed; review its current version", code="DOCUMENT_VERSION_CONFLICT"
            )
        original = (source.metadata_json or {}).get("_persisted_original") or {
            "sha256": source.content_sha256
        }
        new_digest = sha256(content).hexdigest()
        if original["sha256"] != expected_sha256 and (force_reingest or original["sha256"] != new_digest):
            raise ConflictException(
                "Document content changed; reload its current version", code="CONTENT_VERSION_CONFLICT"
            )
        filters = [
            KnowledgeChunkRow.tenant_id == tenant_id,
            KnowledgeChunkRow.workspace_id == workspace_id,
            KnowledgeChunkRow.source_id == source_id,
        ]
        # This read unit ends before admission or model work; no long FOR UPDATE lock.
        async with sources.session() as session:
            previous_count = (
                await session.execute(select(func.count()).select_from(KnowledgeChunkRow).where(*filters))
            ).scalar_one()
            previous_ids = list(
                (
                    await session.execute(
                        select(KnowledgeChunkRow.id)
                        .where(*filters)
                        .order_by(KnowledgeChunkRow.index_in_source, KnowledgeChunkRow.id)
                        .limit(100)
                    )
                ).scalars()
            )
        if original["sha256"] == new_digest and not force_reingest:
            if authorize_commit is not None:
                await authorize_commit()
            return {
                "previous_chunk_count": previous_count,
                "invalidated_chunk_ids": [],
                "chunk_ids_complete": True,
                "n_chunks": source.n_chunks,
                "unchanged": True,
                "source_version_id": head["version_id"] if head else None,
                "extraction_id": head["extraction_id"] if head else None,
            }
        async with domains.model_connections(
            "canon",
            tenant_id,
            workspace_id,
            actor,
            purpose="ingest",
            roles=("documents.embedding",),
            catalog_workspace_id=catalog_workspace_id,
        ):
            updated = await domains._resolve(IntakeService).replace(
                source_id=source_id,
                request=SubmitSourceRequest(),
                content=content,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                filename=filename,
                actor=actor,
                logical_source_key=logical_source_key,
                operation_id=operation_id,
                expected_source_version_id=expected_source_version_id,
                expected_extraction_id=expected_extraction_id,
                authorize_commit=authorize_commit,
            )
        receipt = (updated.metadata_json or {}).get("_source_lineage") or {}
        if not receipt.get("version_id") or not receipt.get("extraction_id"):
            from pyfly.kernel import ServiceUnavailableException

            raise ServiceUnavailableException(
                "The document commit receipt is unavailable", code="DOCUMENT_LINEAGE_UNAVAILABLE"
            )
        return {
            "previous_chunk_count": previous_count,
            "invalidated_chunk_ids": previous_ids,
            "chunk_ids_complete": previous_count <= len(previous_ids),
            "n_chunks": updated.n_chunks,
            "unchanged": False,
            "source_version_id": receipt["version_id"],
            "extraction_id": receipt["extraction_id"],
        }
