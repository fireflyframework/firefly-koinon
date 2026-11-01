# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.evidence.http import private_json
from koinon.knowledge.availability.dtos import AvailabilityRequest, ProcessingRequest
from koinon.knowledge.availability.service import KnowledgeAvailabilityService
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.availability_controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class KnowledgeAvailabilityController:
    def __init__(self, availability: KnowledgeAvailabilityService):
        self.availability = availability

    @post_mapping("/catalog/availability")
    async def observe(
        self, tenant_id: PathVar[str], body: Valid[Body[AvailabilityRequest]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.availability.observe(identity_from_request(request).subject, tenant_id, body)
        )

    @post_mapping("/knowledge-processing")
    async def processing(
        self, tenant_id: PathVar[str], body: Valid[Body[ProcessingRequest]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.availability.processing(identity_from_request(request).subject, tenant_id, body)
        )
