# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed reader-aware reads preserve existing domain services and release fences."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.assistants.history.service import ChatHistoryService
from koinon.integrations.content_sources.read_dtos import ReaderReadInput
from koinon.integrations.content_sources.read_requests import reader_response
from koinon.integrations.content_sources.read_service import SourceReader


@rest_controller(name="assistants.history.read_controller")
@request_mapping("/api/v1/tenants/{tenant_id}/chat")
class ChatHistoryReadController:
    def __init__(self, history: ChatHistoryService, reader: SourceReader):
        self.history = history
        self.reader = reader

    @post_mapping("/threads/{thread_id}/read")
    async def thread_read(
        self,
        tenant_id: PathVar[str],
        thread_id: PathVar[str],
        body: Valid[Body[ReaderReadInput]],
        request: Request,
    ) -> Response:
        async def read(actor):
            return await self.history.get_thread(actor, tenant_id, thread_id)

        return await reader_response(self.reader, request, tenant_id, body, read)
