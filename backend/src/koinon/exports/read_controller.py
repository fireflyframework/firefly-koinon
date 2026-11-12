# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-aware export metadata and binary reads."""

from hashlib import sha256

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.exports.service import KnowledgeExports
from koinon.integrations.content_sources.read_dtos import ReaderReadInput
from koinon.integrations.content_sources.read_requests import reader_response
from koinon.integrations.content_sources.read_service import SourceReader


@rest_controller(name="exports.read_controller")
@request_mapping("/api/v1/tenants/{tenant_id}/exports")
class ExportReadController:
    def __init__(self, exports: KnowledgeExports, reader: SourceReader):
        self.exports, self.reader = exports, reader

    @post_mapping("/{export_id}/read")
    async def get_read(
        self,
        tenant_id: PathVar[str],
        export_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.exports.get(actor, tenant_id, export_id)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/{export_id}/download/read")
    async def download_read(
        self,
        tenant_id: PathVar[str],
        export_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            rendered = await self.exports.download(actor, tenant_id, export_id)
            return Response(
                rendered.content,
                media_type=rendered.content_type,
                headers={
                    **dict(rendered.headers),
                    "Content-Disposition": f'attachment; filename="{rendered.filename}"',
                    "ETag": '"' + sha256(rendered.content).hexdigest() + '"',
                },
            )

        return await reader_response(self.reader, request, tenant_id, body, read)
