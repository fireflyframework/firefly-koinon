# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.organization_knowledge.dtos import OrganizationKnowledgeSettingsInput
from koinon.organization_knowledge.transitions.dtos import (
    KnowledgeModeCurrentView,
    KnowledgeModeRecoveryPage,
    KnowledgeModeRevisionInput,
    KnowledgeModeTargetPage,
    KnowledgeModeTransitionView,
)
from koinon.organization_knowledge.transitions.service import KnowledgeModeTransitions
from koinon.security.identity import identity_from_request


@rest_controller(name="organization_knowledge.mode_controller")
@request_mapping("/api/v1/tenants/{tenant_id}/knowledge/settings/transitions")
class KnowledgeModeController:
    def __init__(self, transitions: KnowledgeModeTransitions):
        self.transitions = transitions

    @post_mapping("", status_code=202)
    async def create(
        self,
        tenant_id: PathVar[str],
        body: Valid[Body[OrganizationKnowledgeSettingsInput]],
        request: Request,
    ) -> KnowledgeModeTransitionView:
        return await self.transitions.request(
            identity_from_request(request).subject,
            tenant_id,
            body,
            request.headers.get("Idempotency-Key", ""),
        )

    @get_mapping("/current")
    async def current(self, tenant_id: PathVar[str], request: Request) -> KnowledgeModeCurrentView:
        return KnowledgeModeCurrentView(
            transition=await self.transitions.current(identity_from_request(request).subject, tenant_id)
        )

    @get_mapping("/{transition_id}")
    async def get(
        self,
        tenant_id: PathVar[str],
        transition_id: PathVar[str],
        request: Request,
    ) -> KnowledgeModeTransitionView:
        return await self.transitions.get(identity_from_request(request).subject, tenant_id, transition_id)

    @get_mapping("/{transition_id}/targets")
    async def targets(
        self,
        tenant_id: PathVar[str],
        transition_id: PathVar[str],
        request: Request,
        after: QueryParam[str | None] = None,
        limit: QueryParam[int] = 50,
    ) -> KnowledgeModeTargetPage:
        return await self.transitions.target_page(
            identity_from_request(request).subject, tenant_id, transition_id, after=after, limit=limit
        )

    @get_mapping("/{transition_id}/recoveries")
    async def recoveries(
        self,
        tenant_id: PathVar[str],
        transition_id: PathVar[str],
        request: Request,
        after: QueryParam[str | None] = None,
        limit: QueryParam[int] = 50,
    ) -> KnowledgeModeRecoveryPage:
        return await self.transitions.recovery_page(
            identity_from_request(request).subject,
            tenant_id,
            transition_id,
            after=after,
            limit=limit,
        )

    @post_mapping("/{transition_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        transition_id: PathVar[str],
        body: Valid[Body[KnowledgeModeRevisionInput]],
        request: Request,
    ) -> KnowledgeModeTransitionView:
        return await self.transitions.cancel(
            identity_from_request(request).subject,
            tenant_id,
            transition_id,
            expected_revision=body.expected_revision,
        )

    @post_mapping("/{transition_id}/retry", status_code=202)
    async def retry(
        self,
        tenant_id: PathVar[str],
        transition_id: PathVar[str],
        body: Valid[Body[KnowledgeModeRevisionInput]],
        request: Request,
    ) -> KnowledgeModeTransitionView:
        return await self.transitions.retry(
            identity_from_request(request).subject,
            tenant_id,
            transition_id,
            expected_revision=body.expected_revision,
        )
