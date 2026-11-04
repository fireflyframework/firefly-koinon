# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Prepare exact whole views from committed sections without embedding or vector writes."""

from collections.abc import Awaitable, Callable

from koinon_storage.cloud import ObjectIntegrityError, ObjectTooLargeError
from pyfly.container import service
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.adapters import NativeDomains, native_scope


@service(name="organization_knowledge.mode_document_views")
class ModeDocumentViews:
    def __init__(self, domains: NativeDomains):
        self.domains = domains

    async def prepare(
        self,
        *,
        tenant_id,
        workspace_id,
        source_id,
        actor,
        authorize: Callable[[], Awaitable[None]],
        publication_guard=None,
    ):
        from flycanon.core.services.sources.lineage.dtos import DocumentScope
        from flycanon.core.services.sources.lineage.service import DocumentLineage
        from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
        from flycanon.models.repositories.source_repository import SourceRepository

        await authorize()
        with native_scope("canon", tenant_id, workspace_id, actor):
            source = await self.domains._resolve(SourceRepository).get(
                source_id, tenant_id=tenant_id, workspace_id=workspace_id
            )
            if source is None or source.status != "ingested":
                raise ServiceUnavailableException(
                    "Finish processing this document before preparing its whole view",
                    code="SOURCE_PROCESSING_REQUIRED",
                )
            lineage = self.domains._resolve(DocumentLineage)
            scope = DocumentScope(tenant_id, workspace_id, actor)
            reader = WholeDocumentReader(lineage)
            try:
                pin = await reader.pin(scope, source_id)
            except ServiceUnavailableException as error:
                if error.code != "DOCUMENT_EXTRACTION_UNAVAILABLE":
                    raise
                raise ServiceUnavailableException(
                    "This older source has no committed document version. Open its document processing "
                    "action before retrying; changing mode does not configure embeddings or reprocess it.",
                    code="SOURCE_VERSION_PREPARATION_REQUIRED",
                ) from error

            async def current():
                await authorize()
                head = await lineage.head(scope, source_id)
                if head is None or (head["version_id"], head["extraction_id"]) != (
                    pin.source_version_id,
                    pin.ingestion_extraction_id,
                ):
                    raise ConflictException(
                        "Document version changed during preparation", code="DOCUMENT_VERSION_CONFLICT"
                    )

            try:
                read = await reader.read(
                    scope,
                    source_id=source_id,
                    source_version_id=pin.source_version_id,
                    ingestion_extraction_id=pin.ingestion_extraction_id,
                    authorize=current,
                    publication_guard=publication_guard,
                )
            except ObjectIntegrityError as error:
                raise ServiceUnavailableException(
                    "The stored original no longer matches its recorded file receipt",
                    code="DOCUMENT_ORIGINAL_INTEGRITY_FAILED",
                ) from error
            except ObjectTooLargeError as error:
                raise ServiceUnavailableException(
                    "The document exceeds the configured whole-view preparation limit",
                    code="DOCUMENT_VIEW_LIMIT",
                ) from error
            await current()
            return {
                "source_version_id": read.source_version_id,
                "ingestion_extraction_id": read.ingestion_extraction_id,
                "view_extraction_id": read.extraction_id,
                "raw_sha256": read.raw_sha256,
                "raw_bytes": pin.raw_bytes,
                "normalized_sha256": read.normalized_sha256,
                "parts": len(read.pages),
                "text_bytes": sum(len(page.text.encode()) for page in read.pages),
            }

    async def verify_pins(self, *, tenant_id, workspace_id, actor, pins):
        """Recheck metadata in bounded batches after the original bytes were verified."""
        from flycanon.core.services.sources.lineage.dtos import DocumentScope
        from flycanon.core.services.sources.lineage.ports import LineageQuery
        from flycanon.core.services.sources.lineage.service import DocumentLineage

        if not 1 <= len(pins) <= 200:
            raise ValueError("Recorded-view verification requires 1 to 200 exact pins")
        with native_scope("canon", tenant_id, workspace_id, actor):
            lineage = self.domains._resolve(DocumentLineage)
            scope = DocumentScope(tenant_id, workspace_id, actor)
            async with lineage.repository.read() as unit:
                heads = {
                    row["source_id"]: row
                    for row in await unit.all(
                        LineageQuery(
                            "head", scope, included={"source_id": [pin["source_id"] for pin in pins]}
                        )
                    )
                }
                versions = {
                    row["id"]: row
                    for row in await unit.all(
                        LineageQuery(
                            "version", scope, included={"id": [pin["source_version_id"] for pin in pins]}
                        )
                    )
                }
                views = {
                    row["id"]: row
                    for row in await unit.all(
                        LineageQuery(
                            "extraction",
                            scope,
                            equal={"purpose": "whole_document_read"},
                            included={"id": [pin["view_extraction_id"] for pin in pins]},
                        )
                    )
                }
                artifacts = {
                    row["id"]: row
                    for row in await unit.all(
                        LineageQuery(
                            "artifact",
                            scope,
                            included={
                                "id": [
                                    *[version["artifact_id"] for version in versions.values()],
                                    *[view["normalized_artifact_id"] for view in views.values()],
                                ]
                            },
                        )
                    )
                }
                current_count = await unit.count(
                    LineageQuery(
                        "source",
                        scope,
                        equal={"status": "ingested"},
                        included={"id": [pin["source_id"] for pin in pins]},
                    )
                )
            if current_count != len({pin["source_id"] for pin in pins}):
                raise ConflictException(
                    "A prepared source is no longer processed", code="SOURCE_PROCESSING_REQUIRED"
                )
            for pin in pins:
                head, version, view = (
                    heads.get(pin["source_id"]),
                    versions.get(pin["source_version_id"]),
                    views.get(pin["view_extraction_id"]),
                )
                if (
                    head is None
                    or version is None
                    or view is None
                    or head["version_id"] != pin["source_version_id"]
                    or head["extraction_id"] != pin["ingestion_extraction_id"]
                    or version["source_id"] != pin["source_id"]
                    or artifacts.get(version["artifact_id"], {}).get("sha256") != pin["raw_sha256"]
                    or artifacts.get(version["artifact_id"], {}).get("bytes") != pin["raw_bytes"]
                    or artifacts.get(view["normalized_artifact_id"], {}).get("sha256")
                    != pin["normalized_sha256"]
                    or view["source_id"] != pin["source_id"]
                    or view["version_id"] != pin["source_version_id"]
                    or view["projection"].get("input_extraction_id") != pin["ingestion_extraction_id"]
                ):
                    raise ConflictException(
                        "A prepared document version changed before activation",
                        code="DOCUMENT_VERSION_CONFLICT",
                        context={"source_id": pin["source_id"]},
                    )

    async def verify_sources(self, *, tenant_id, workspace_id, actor, source_ids):
        from flycanon.models.repositories.source_repository import SourceRepository

        if not 1 <= len(source_ids) <= 200:
            raise ValueError("Source verification requires 1 to 200 exact identifiers")
        with native_scope("canon", tenant_id, workspace_id, actor):
            rows = await self.domains._resolve(SourceRepository).get_many_scoped(
                source_ids, tenant_id=tenant_id, workspace_id=workspace_id, statuses=("ingested",)
            )
        if {row.id for row in rows} != set(source_ids):
            present = {row.id for row in rows}
            raise ConflictException(
                "A document has not completed processing",
                code="SOURCE_PROCESSING_REQUIRED",
                context={
                    "source_id": next(identifier for identifier in source_ids if identifier not in present)
                },
            )
