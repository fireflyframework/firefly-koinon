# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Strict product intake: admit, transform without locks, then compare and promote."""

import contextlib
from collections.abc import Awaitable, Callable, Sequence
from typing import Any
from uuid import uuid4

from pyfly.container import service
from pyfly.kernel import ConflictException, ServiceUnavailableException

from flycanon.core.mappers.intake_mapper import _metadata_to_json
from flycanon.core.services.embeddings.embedding_sets import bind_embedding_set
from flycanon.core.services.sources.intake_events import publish_success
from flycanon.core.services.sources.intake_runtime import SourceIntakeComponents
from flycanon.core.services.sources.intake_transforms import (
    apply_pii_policy,
    embedder_for,
    first_text,
    merge_artifacts,
)
from flycanon.core.services.sources.lineage.capture import artifact, manifest, signature
from flycanon.core.services.sources.lineage.dtos import Admission, DocumentScope
from flycanon.core.services.sources.lineage.ports import LineageQuery, LineageRecord
from flycanon.core.services.sources.lineage.service import DocumentLineage, identity
from flycanon.interfaces.dtos.ingestion import IngestionResult
from flycanon.interfaces.dtos.source import SubmitSourceRequest
from flycanon.interfaces.enums import SourceKind
from flycanon.models.entities.source import SourceRow


@service(name="canon.DocumentLineagePipeline")
class DocumentLineagePipeline:
    def __init__(self, components: SourceIntakeComponents, lineage: DocumentLineage):
        self.components = components
        self.lineage = lineage

    async def run(
        self,
        *,
        request: SubmitSourceRequest,
        content: bytes,
        tenant_id: str,
        workspace_id: str,
        actor: str | None,
        filename: str | None,
        content_type: str | None,
        logical_key: str,
        operation_id: str,
        source_id: str | None = None,
        expected_source_version_id: str | None = None,
        expected_extraction_id: str | None = None,
        authorize_commit: Callable[[], Awaitable[None]] | None = None,
        correlation_id: str | None = None,
    ) -> SourceRow:
        service = self.components
        if not service.settings.store_originals:
            raise ServiceUnavailableException(
                "Durable originals must be enabled before processing", code="DOCUMENT_ORIGINAL_UNAVAILABLE"
            )
        if service.settings.vector_store != "pgvector":
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
            return await service.source_repository.get(
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
        self,
        scope: DocumentScope,
        admission: Admission,
        request: SubmitSourceRequest,
        content: bytes,
        filename: str | None,
        content_type: str | None,
        authorize_commit: Callable[[], Awaitable[None]] | None,
        correlation_id: str | None,
    ) -> SourceRow:
        service = self.components
        outputs = await service.binary_normalizer.normalise(
            content, declared_media_type=content_type, filename=filename
        )
        observations = []
        merged_kind, merged, metadata = merge_artifacts(
            outputs, filename, loaders=service.loaders, observer=lambda *record: observations.append(record)
        )
        processed, metadata = apply_pii_policy(
            merged, metadata, policy=service.pii_policy, scanner=service.pii_scanner
        )
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
        result = service.ingestion.ingest(
            source=source, content=processed, tenant_id=scope.tenant_id, workspace_id=scope.workspace_id
        )
        first = outputs[0] if outputs else None
        extracted = service.metadata_extractor.extract(
            first.bytes if first else processed,
            media_type=first.media_type if first else content_type or "",
            filename=filename,
            text_sample=first_text(result.chunks),
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
                    signature(service.binary_normalizer),
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
            ("merge", record["id"], merged_artifact["id"], signature(merge_artifacts), {})
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
                {"policy": service.pii_policy.value},
                {},
            )
        )
        binding, embedder = await embedder_for(
            tenant_id=scope.tenant_id,
            workspace_id=scope.workspace_id,
            embeddings=service.embeddings,
            embedding_sets=service.embedding_sets,
            embedding_registry=service.embedding_registry,
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
        scope: DocumentScope,
        admission: Admission,
        result: IngestionResult,
        artifacts: list[LineageRecord],
        edges: list[tuple[str, str, str, dict[str, Any], dict[str, Any]]],
        normalized: LineageRecord,
        embeddings: Sequence[Sequence[float]],
        embedding_model: str,
        authorize_commit: Callable[[], Awaitable[None]] | None,
        correlation_id: str | None,
    ) -> SourceRow:
        service, source = self.components, result.source
        extraction_id = str(uuid4())
        parts = manifest(scope, admission, result, extraction_id, normalized["id"])
        implementation = {
            "loader": signature(service.loaders.get(SourceKind(source.kind))),
            "chunker": signature(service.ingestion.chunker),
        }
        source.object_store_key = admission.object_key
        source.metadata_json = {
            **source.metadata_json,
            "_persisted_original": {"sha256": admission.sha256, "bytes": admission.bytes},
            "_source_lineage": {"version_id": admission.version_id, "extraction_id": extraction_id},
        }
        if authorize_commit is not None:
            await authorize_commit()
        async with self.lineage.repository.write() as session:
            head = await session.one(LineageQuery("head", scope, source_id=source.id, lock="update"))
            if (head["version_id"], head["extraction_id"]) != (
                admission.expected_version_id,
                admission.expected_extraction_id,
            ):
                raise ConflictException(
                    "Document changed during processing; review its current version",
                    code="DOCUMENT_VERSION_CONFLICT",
                )
            await session.perform(
                LineageQuery(
                    "source",
                    scope,
                    lock="update",
                    equal={"id": source.id, "tenant_id": scope.tenant_id, "workspace_id": scope.workspace_id},
                )
            )
            base = identity(scope, source.id)
            if artifacts:
                await session.insert("artifact", artifacts)
            await session.insert(
                "extraction",
                dict(
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
                ),
            )
            for ordinal, (stage, input_id, output_id, observed, parameters) in enumerate(edges):
                await session.insert(
                    "step",
                    dict(
                        id=str(uuid4()),
                        **base,
                        extraction_id=extraction_id,
                        ordinal=ordinal,
                        stage=stage,
                        input_artifact_id=input_id,
                        output_artifact_id=output_id,
                        implementation=observed,
                        parameters=parameters,
                    ),
                )
            if parts:
                await session.insert("part", parts)
            updated = await service.source_repository.update(source)
            await service.chunk_repository.replace_for_source(source.id, result.chunks)
            await service.indexer.replace_for_source(
                source=updated,
                chunks=result.chunks,
                embeddings=embeddings,
                embedding_model=embedding_model,
                tenant_id=scope.tenant_id,
                workspace_id=scope.workspace_id,
            )
            await session.update(
                LineageQuery("head", scope, source_id=source.id),
                dict(version_id=admission.version_id, extraction_id=extraction_id),
            )
            await session.insert(
                "event",
                dict(
                    id=str(uuid4()),
                    **base,
                    version_id=admission.version_id,
                    extraction_id=extraction_id,
                    status="committed",
                ),
            )
            await service.audit.record(
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
        await publish_success(
            service.event_publisher, service.settings, source=updated, correlation_id=correlation_id
        )
        return updated
