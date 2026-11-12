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
from koinon.sharing.service import ConversationShares


@rest_controller(name="sharing.read_controller")
@request_mapping("/api/v1/tenants/{tenant_id}/shares")
class ShareReadController:
    def __init__(self, shares: ConversationShares, reader: SourceReader):
        self.shares = shares
        self.reader = reader

    @post_mapping("/{share_id}/read")
    async def get_read(
        self,
        tenant_id: PathVar[str],
        share_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.shares.read(actor, tenant_id, share_id)

        return await reader_response(self.reader, request, tenant_id, body, read)
