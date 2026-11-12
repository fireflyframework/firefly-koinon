# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed reader-aware reads preserve existing domain services and release fences."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.integrations.content_sources.read_dtos import ReaderReadInput
from koinon.integrations.content_sources.read_requests import reader_response
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.knowledge.document_history.download_response import original_file_response
from koinon.knowledge.document_history.downloads import OriginalDownloads
from koinon.knowledge.document_history.read_dtos import DocumentChunksReadInput, LineageReadInput
from koinon.knowledge.service import KnowledgeFacade


@rest_controller(name="knowledge.read_controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class KnowledgeReadController:
    def __init__(self, knowledge: KnowledgeFacade, downloads: OriginalDownloads, reader: SourceReader):
        self.knowledge, self.downloads = knowledge, downloads
        self.reader = reader

    @post_mapping("/datasets/{dataset_id}/schema/read")
    async def schema_read(
        self,
        tenant_id: PathVar[str],
        dataset_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.knowledge.schema(actor, tenant_id, dataset_id)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/lineage/read")
    async def lineage_read(
        self,
        tenant_id: PathVar[str],
        body: Valid[Body[LineageReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.knowledge.lineage(actor, tenant_id, body.asset_id)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/documents/{document_id}/chunks/read")
    async def document_chunks_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        body: Valid[Body[DocumentChunksReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.knowledge.document_chunks(
                actor, tenant_id, document_id, **body.model_dump(exclude={"reader_source_connections"})
            )

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/documents/{document_id}/original/read")
    async def document_original_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await original_file_response(
                await self.downloads.open(
                    actor, tenant_id, document_id, context=request.state.security_context
                )
            )

        return await reader_response(self.reader, request, tenant_id, body, read)
