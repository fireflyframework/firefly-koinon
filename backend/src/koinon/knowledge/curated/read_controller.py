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
from koinon.knowledge.curated.reads import CuratedKnowledgeReads


@rest_controller(name="knowledge.curated.read_controller")
@request_mapping("/api/v1/tenants/{tenant_id}/knowledge-items")
class CuratedKnowledgeReadController:
    def __init__(self, reads: CuratedKnowledgeReads, reader: SourceReader):
        self.reads = reads
        self.reader = reader

    @post_mapping("/{item_id}/read")
    async def get_read(
        self,
        tenant_id: PathVar[str],
        item_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.reads.version(actor, tenant_id, item_id)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/{item_id}/versions/{version}/read")
    async def version_read(
        self,
        tenant_id: PathVar[str],
        item_id: PathVar[str],
        version: PathVar[int],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.reads.version(actor, tenant_id, item_id, version)

        return await reader_response(self.reader, request, tenant_id, body, read)
