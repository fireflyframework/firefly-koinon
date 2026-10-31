# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request
from starlette.responses import JSONResponse

from koinon.evidence.http import private_json
from koinon.knowledge.external_reviews.dtos import ExternalReviewDecision, ExternalReviewInput
from koinon.knowledge.external_reviews.service import ExternalKnowledgeReviews
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.external_reviews.controller")
@request_mapping("/api/v1/tenants/{tenant_id}/external-knowledge-reviews")
class ExternalKnowledgeReviewController:
    def __init__(self, reviews: ExternalKnowledgeReviews):
        self.reviews = reviews

    @post_mapping("", status_code=201)
    async def stage(
        self, tenant_id: PathVar[str], body: Valid[Body[ExternalReviewInput]], request: Request
    ) -> JSONResponse:
        return private_json(
            await self.reviews.stage(
                identity_from_request(request).subject,
                tenant_id,
                body.model_dump(mode="json"),
                request.headers.get("Idempotency-Key", ""),
            ),
            status=201,
        )

    @get_mapping("/{review_id}")
    async def get(self, tenant_id: PathVar[str], review_id: PathVar[str], request: Request) -> JSONResponse:
        return private_json(
            await self.reviews.get(identity_from_request(request).subject, tenant_id, review_id)
        )

    @post_mapping("/{review_id}/approve")
    async def approve(
        self,
        tenant_id: PathVar[str],
        review_id: PathVar[str],
        body: Valid[Body[ExternalReviewDecision]],
        request: Request,
    ) -> JSONResponse:
        outcome = await self.reviews.approve(
            identity_from_request(request).subject,
            tenant_id,
            review_id,
            body.model_dump(mode="json"),
            request.headers.get("Idempotency-Key", ""),
        )
        return private_json(outcome, status=202 if outcome.status == "pending" else 200)

    @post_mapping("/{review_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        review_id: PathVar[str],
        body: Valid[Body[ExternalReviewDecision]],
        request: Request,
    ) -> JSONResponse:
        return private_json(
            await self.reviews.cancel(
                identity_from_request(request).subject, tenant_id, review_id, body.model_dump(mode="json")
            )
        )
