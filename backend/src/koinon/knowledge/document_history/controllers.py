# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

from pyfly.container import rest_controller
from pyfly.web import PathVar, QueryParam, get_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.knowledge.document_history.download_response import original_file_response
from koinon.knowledge.document_history.downloads import OriginalDownloads
from koinon.knowledge.document_history.dtos import (
    DocumentExtractionPage,
    DocumentPartContent,
    DocumentPartPage,
    DocumentVersion,
    DocumentVersionPage,
)
from koinon.knowledge.document_history.service import DocumentHistoryService
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.document_history")
@request_mapping("/api/v1/tenants/{tenant_id}/documents/{document_id}/versions")
class DocumentHistoryController:
    def __init__(self, history: DocumentHistoryService, downloads: OriginalDownloads):
        self.history = history
        self.downloads = downloads

    @get_mapping("")
    async def versions(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> DocumentVersionPage:
        return await self.history.versions(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            page=page,
            page_size=page_size,
        )

    @get_mapping("/{source_version_id}")
    async def version(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        request: Request,
    ) -> DocumentVersion:
        return await self.history.version(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            source_version_id,
        )

    @get_mapping("/{source_version_id}/extractions")
    async def extractions(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> DocumentExtractionPage:
        return await self.history.extractions(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            source_version_id,
            page=page,
            page_size=page_size,
        )

    @get_mapping("/{source_version_id}/extractions/{extraction_id}/parts")
    async def parts(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        extraction_id: PathVar[str],
        request: Request,
        kind: QueryParam[str | None] = None,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> DocumentPartPage:
        return await self.history.parts(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            source_version_id,
            extraction_id,
            kind=kind,
            page=page,
            page_size=page_size,
        )

    @get_mapping("/{source_version_id}/extractions/{extraction_id}/parts/{source_part_id}")
    async def part(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        extraction_id: PathVar[str],
        source_part_id: PathVar[str],
        request: Request,
    ) -> DocumentPartContent:
        return await self.history.part(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            source_version_id,
            extraction_id,
            source_part_id,
        )

    @get_mapping("/{source_version_id}/original")
    async def original(
        self,
        tenant_id: PathVar[str],
        document_id: PathVar[str],
        source_version_id: PathVar[str],
        request: Request,
    ) -> Response:
        download = await self.downloads.open(
            identity_from_request(request).subject,
            tenant_id,
            document_id,
            source_version_id=source_version_id,
            context=request.state.security_context,
        )
        return await original_file_response(download)
