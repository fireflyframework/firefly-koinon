# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Strict product intake: admit, transform without locks, then compare and promote."""

import contextlib
from uuid import uuid4

from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import insert, select, update

from flycanon.core.services.embeddings.embedding_sets import bind_embedding_set
from flycanon.core.services.sources.lineage.capture import artifact, manifest, signature
from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.core.services.sources.lineage.service import DocumentLineage, conditions, identity
from flycanon.interfaces.enums import SourceKind
from flycanon.models.entities.source import SourceRow
from flycanon.models.entities.source_lineage import (
    source_artifacts,
    source_events,
    source_extractions,
    source_heads,
    source_parts,
    source_steps,
)


class DocumentLineagePipeline:
    def __init__(self, intake):
        self.intake = intake
        self.lineage = DocumentLineage(intake._sources, intake._object_store)

    async def run(
        self,
        *,
        request,
        content,
        tenant_id,
        workspace_id,
        actor,
        filename,
        content_type,
        logical_key,
        operation_id,
        source_id=None,
        expected_source_version_id=None,
        expected_extraction_id=None,
        authorize_commit=None,
        correlation_id=None,
    ):
        service = self.intake
        if not service._settings.store_originals:
            raise ServiceUnavailableException(
                "Durable originals must be enabled before processing", code="DOCUMENT_ORIGINAL_UNAVAILABLE"
            )
        if service._settings.vector_store != "pgvector":
            raise ServiceUnavailableException(
                "Immutable document promotion requires the native transactional index",
                code="DOCUMENT_LINEAGE_INDEX_REQUIRED",
            )
        scope = DocumentScope(tenant_id, str(workspace_id), actor or "")
        await self.lineage.require_schema()
        admission = await self.lineage.admit(
            scope,
            logical_key=logical_key,
            operation_id=operation_id,
            content=content,
            filename=filename,
            media_type=content_type,
            source_id=source_id,
            expected_source_version_id=expected_source_version_id,
            expected_extraction_id=expected_extraction_id,
        )
        completed = await self.lineage.committed(scope, admission.source_id, admission.version_id)
        if completed is not None:
            head = await self.lineage.head(scope, admission.source_id)
            if head is None or head["extraction_id"] != completed["id"]:
                raise ConflictException(
                    "This completed document operation has been superseded",
                    code="DOCUMENT_OPERATION_SUPERSEDED",
                )
            return await service._sources.get(
                admission.source_id, tenant_id=tenant_id, workspace_id=workspace_id
            )
        try:
            return await self._transform(
                scope, admission, request, content, filename, content_type, authorize_commit, correlation_id
            )
        except Exception as error:
            await self.lineage.failed(scope, admission, type(error).__name__)
            raise

    async def _transform(
        self, scope, admission, request, content, filename, content_type, authorize_commit, correlation_id
    ):
        from flycanon.core.services.sources.intake_service import _metadata_to_json

        service = self.intake
        outputs = await service._binary_normalizer.normalise(
            content, declared_media_type=content_type, filename=filename
        )
        observations = []
        merged_kind, merged, metadata = service._merge_artifacts(
            outputs, filename, observer=lambda *record: observations.append(record)
        )
        processed, metadata = service._apply_pii_policy(merged, metadata)
        source = SourceRow(
            id=admission.source_id,
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            kind=(request.kind if request.kind != SourceKind.unknown else merged_kind).value,
            status="pending",
            filename=filename,
            uri=request.uri,
            content_type=content_type,
            content_sha256="",
            content_bytes=0,
            metadata_json={**_metadata_to_json(request.metadata), **metadata},
        )
        result = service._ingestion.ingest(
            source=source, content=processed, tenant_id=scope.tenant_id, workspace_id=scope.workspace_id
        )
        first = outputs[0] if outputs else None
        extracted = service._metadata.extract(
            first.bytes if first else processed,
            media_type=first.media_type if first else content_type or "",
            filename=filename,
            text_sample=service._first_text(result.chunks),
        )
        source.metadata_json = {**source.metadata_json, "extracted": extracted.to_dict()}
        artifacts, edges = [], []
        included = {index for index, _, used, _ in observations if used} if observations else {0}
        for index, output in enumerate(outputs):
            record = await artifact(
                self.lineage, scope, source.id, output.bytes, "normalizer_output", output.media_type
            )
            artifacts.append(record)
            edges.append(
                (
                    "normalize",
                    admission.artifact_id,
                    record["id"],
                    signature(service._binary_normalizer),
                    {
                        "filename": output.filename,
                        "kind": str(output.kind),
                        "derived_from": list(output.derived_from),
                        "merge_included": index in included,
                        "merge_reason": next(
                            (reason for child, _, _, reason in observations if child == index), None
                        ),
                    },
                )
            )
        merged_artifact = await artifact(
            self.lineage, scope, source.id, merged, "merged", "application/octet-stream"
        )
        artifacts.append(merged_artifact)
        edges.extend(
            ("merge", record["id"], merged_artifact["id"], signature(service), {})
            for index, record in enumerate(artifacts[:-1])
            if index in included
        )
        processed_artifact = await artifact(
            self.lineage, scope, source.id, processed, "normalized", "application/octet-stream"
        )
        artifacts.append(processed_artifact)
        edges.append(
            (
                "pii_policy",
                merged_artifact["id"],
                processed_artifact["id"],
                {"policy": service._pii_policy.value},
                {},
            )
        )
        binding, embedder = await service._embedder_for(
            tenant_id=scope.tenant_id, workspace_id=scope.workspace_id
        )
        with bind_embedding_set(binding) if binding is not None else contextlib.nullcontext():
            embeddings = await embedder.embed([chunk.content for chunk in result.chunks])
            for chunk in result.chunks:
                chunk.embedding_model = embedder.model
            return await self._promote(
                scope,
                admission,
                result,
                artifacts,
                edges,
                processed_artifact,
                embeddings,
                embedder.model,
                authorize_commit,
                correlation_id,
            )

    async def _promote(
        self,
        scope,
        admission,
        result,
        artifacts,
        edges,
        normalized,
        embeddings,
        embedding_model,
        authorize_commit,
        correlation_id,
    ):
        service, source = self.intake, result.source
        extraction_id = str(uuid4())
        parts = manifest(scope, admission, result, extraction_id, normalized["id"])
        implementation = {
            "loader": signature(service._loaders.get(SourceKind(source.kind))),
            "chunker": signature(service._ingestion._chunker),
        }
        source.object_store_key = admission.object_key
        source.metadata_json = {
            **source.metadata_json,
            "_persisted_original": {"sha256": admission.sha256, "bytes": admission.bytes},
            "_source_lineage": {"version_id": admission.version_id, "extraction_id": extraction_id},
        }
        if authorize_commit is not None:
            await authorize_commit()
        async with self.lineage.unit() as session:
            head = (
                (
                    await session.execute(
                        select(source_heads)
                        .where(*conditions(source_heads, scope, source.id))
                        .with_for_update()
                    )
                )
                .mappings()
                .one()
            )
            if (head["version_id"], head["extraction_id"]) != (
                admission.expected_version_id,
                admission.expected_extraction_id,
            ):
                raise ConflictException(
                    "Document changed during processing; review its current version",
                    code="DOCUMENT_VERSION_CONFLICT",
                )
            await session.execute(
                select(SourceRow)
                .where(
                    SourceRow.id == source.id,
                    SourceRow.tenant_id == scope.tenant_id,
                    SourceRow.workspace_id == scope.workspace_id,
                )
                .with_for_update()
            )
            base = identity(scope, source.id)
            if artifacts:
                await session.execute(insert(source_artifacts), artifacts)
            await session.execute(
                insert(source_extractions).values(
                    id=extraction_id,
                    **base,
                    version_id=admission.version_id,
                    purpose="ingestion",
                    normalized_artifact_id=normalized["id"],
                    predecessor_id=admission.expected_extraction_id,
                    implementation=implementation,
                    coverage="file_section",
                    projection={
                        "kind": source.kind,
                        "filename": source.filename,
                        "content_sha256": source.content_sha256,
                        "n_chunks": source.n_chunks,
                    },
                )
            )
            for ordinal, (stage, input_id, output_id, observed, parameters) in enumerate(edges):
                await session.execute(
                    insert(source_steps).values(
                        id=str(uuid4()),
                        **base,
                        extraction_id=extraction_id,
                        ordinal=ordinal,
                        stage=stage,
                        input_artifact_id=input_id,
                        output_artifact_id=output_id,
                        implementation=observed,
                        parameters=parameters,
                    )
                )
            if parts:
                await session.execute(insert(source_parts), parts)
            updated = await service._sources.update(source)
            await service._chunks.replace_for_source(source.id, result.chunks)
            await service._indexer.replace_for_source(
                source=updated,
                chunks=result.chunks,
                embeddings=embeddings,
                embedding_model=embedding_model,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
            )
            await session.execute(
                update(source_heads)
                .where(*conditions(source_heads, scope, source.id))
                .values(version_id=admission.version_id, extraction_id=extraction_id)
            )
            await session.execute(
                insert(source_events).values(
                    id=str(uuid4()),
                    **base,
                    version_id=admission.version_id,
                    extraction_id=extraction_id,
                    status="committed",
                )
            )
            await service._audit.record(
                event_type="source.version_committed",
                subject_kind="source",
                subject_id=source.id,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
                actor=scope.actor,
                correlation_id=correlation_id,
                payload={
                    "version_id": admission.version_id,
                    "extraction_id": extraction_id,
                    "raw_sha256": admission.sha256,
                    "n_chunks": source.n_chunks,
                },
            )
        await service._publish_success(source=updated, correlation_id=correlation_id)
        return updated
