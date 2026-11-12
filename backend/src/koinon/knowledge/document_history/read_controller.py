# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed reader-aware reads preserve existing domain services and release fences."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.integrations.content_sources.read_dtos import ReaderPageInput, ReaderReadInput
from koinon.integrations.content_sources.read_requests import reader_response
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.knowledge.document_history.download_response import original_file_response
from koinon.knowledge.document_history.downloads import OriginalDownloads
from koinon.knowledge.document_history.read_dtos import DocumentPartsReadInput
from koinon.knowledge.document_history.service import DocumentHistoryService


@rest_controller(name="knowledge.document_history_read")
@request_mapping("/api/v1/tenants/{tenant_id}/documents/{document_id}/versions")
class DocumentHistoryReadController:
    def __init__(self, history: DocumentHistoryService, downloads: OriginalDownloads, reader: SourceReader):
        self.history, self.downloads = history, downloads
        self.reader = reader

    @post_mapping("/read")
    async def versions_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        body: Valid[Body[ReaderPageInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.history.versions(
                actor, tenant_id, document_id, page=body.page, page_size=body.page_size
            )

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/{source_version_id}/read")
    async def version_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.history.version(actor, tenant_id, document_id, source_version_id)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/{source_version_id}/extractions/read")
    async def extractions_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        body: Valid[Body[ReaderPageInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.history.extractions(
                actor, tenant_id, document_id, source_version_id, page=body.page, page_size=body.page_size
            )

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/{source_version_id}/extractions/{extraction_id}/parts/read")
    async def parts_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        extraction_id: PathVar[str],
        body: Valid[Body[DocumentPartsReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.history.parts(
                actor,
                tenant_id,
                document_id,
                source_version_id,
                extraction_id,
                page=body.page,
                page_size=body.page_size,
                kind=body.kind,
            )

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/{source_version_id}/extractions/{extraction_id}/parts/{source_part_id}/read")
    async def part_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        extraction_id: PathVar[str],
        source_part_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.history.part(
                actor, tenant_id, document_id, source_version_id, extraction_id, source_part_id
            )

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/{source_version_id}/original/read")
    async def original_read(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await original_file_response(
                await self.downloads.open(
                    actor,
                    tenant_id,
                    document_id,
                    source_version_id=source_version_id,
                    context=request.state.security_context,
                )
            )

        return await reader_response(self.reader, request, tenant_id, body, read)
