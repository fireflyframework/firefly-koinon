# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.evidence.http import private_json
from koinon.evidence.service import ConversationEvidence
from koinon.exports.dtos import MessageSelection
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/evidence")
class EvidenceController:
    def __init__(self, evidence: ConversationEvidence):
        self.evidence = evidence

    @post_mapping("/conversations")
    async def conversation(
        self, tenant_id: PathVar[str], body: Valid[Body[MessageSelection]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.evidence.conversation(identity_from_request(request).subject, tenant_id, body)
        )
