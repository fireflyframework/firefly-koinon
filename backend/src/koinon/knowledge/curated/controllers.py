# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.evidence.http import private_json
from koinon.knowledge.curated.dtos import KnowledgeCancellation, KnowledgeConfirmation, KnowledgeIntentInput
from koinon.knowledge.curated.intents import KnowledgeIntents
from koinon.knowledge.curated.reads import CuratedKnowledgeReads
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.curated.controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class CuratedKnowledgeController:
    def __init__(self, intents: KnowledgeIntents, reads: CuratedKnowledgeReads):
        self.intents, self.reads = intents, reads

    @post_mapping("/knowledge-intents", status_code=201)
    async def preview(
        self, tenant_id: PathVar[str], body: Valid[Body[KnowledgeIntentInput]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.intents.preview(
                identity_from_request(request).subject, tenant_id, body.model_dump(mode="json")
            ),
            status=201,
        )

    @get_mapping("/knowledge-intents/{intent_id}")
    async def intent(
        self, tenant_id: PathVar[str], intent_id: PathVar[str], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.intents.get(identity_from_request(request).subject, tenant_id, intent_id)
        )

    @post_mapping("/knowledge-intents/{intent_id}/confirm")
    async def confirm(
        self,
        tenant_id: PathVar[str],
        intent_id: PathVar[str],
        body: Valid[Body[KnowledgeConfirmation]],
        request: Request,
    ) -> JSONResponse:
        outcome = await self.intents.confirm(
            identity_from_request(request).subject,
            tenant_id,
            intent_id,
            body.model_dump(mode="json"),
            request.headers.get("Idempotency-Key", ""),
        )
        return private_json(outcome, status=202 if outcome.status == "pending" else 200)

    @post_mapping("/knowledge-intents/{intent_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        intent_id: PathVar[str],
        body: Valid[Body[KnowledgeCancellation]],
        request: Request,
    ) -> JSONResponse:
        return private_json(
            await self.intents.cancel(
                identity_from_request(request).subject, tenant_id, intent_id, body.expected_revision
            )
        )

    @get_mapping("/knowledge-items")
    async def list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        workspace_id: QueryParam[str | None] = None,
        project_id: QueryParam[str | None] = None,
        destination_id: QueryParam[str | None] = None,
        q: QueryParam[str] = "",
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> JSONResponse:
        return private_json(
            await self.reads.page(
                identity_from_request(request).subject,
                tenant_id,
                workspace_id=workspace_id,
                project_id=project_id,
                destination_id=destination_id,
                q=q,
                page=page,
                page_size=page_size,
            )
        )

    @get_mapping("/knowledge-items/{item_id}")
    async def get(self, tenant_id: PathVar[str], item_id: PathVar[str], request: Request) -> JSONResponse:
        return private_json(
            await self.reads.version(identity_from_request(request).subject, tenant_id, item_id)
        )

    @get_mapping("/knowledge-items/{item_id}/versions/{version}")
    async def version(
        self, tenant_id: PathVar[str], item_id: PathVar[str], version: PathVar[int], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.reads.version(identity_from_request(request).subject, tenant_id, item_id, version)
        )
