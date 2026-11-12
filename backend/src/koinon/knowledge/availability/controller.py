# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import Response

from koinon.integrations.content_sources.read_requests import reader_response
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.knowledge.availability.dtos import AvailabilityRequest, ProcessingRequest
from koinon.knowledge.availability.service import KnowledgeAvailabilityService


@rest_controller(name="knowledge.availability_controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class KnowledgeAvailabilityController:
    def __init__(self, availability: KnowledgeAvailabilityService, reader: SourceReader):
        self.availability = availability
        self.reader = reader

    @post_mapping("/catalog/availability")
    async def observe(
        self, tenant_id: PathVar[str], body: Valid[Body[AvailabilityRequest]], request: Request
    ) -> Response:
        async def read(actor):
            return await self.availability.observe(actor, tenant_id, body)

        return await reader_response(self.reader, request, tenant_id, body, read)

    @post_mapping("/knowledge-processing")
    async def processing(
        self, tenant_id: PathVar[str], body: Valid[Body[ProcessingRequest]], request: Request
    ) -> Response:
        async def read(actor):
            return await self.availability.processing(actor, tenant_id, body)

        return await reader_response(self.reader, request, tenant_id, body, read)
