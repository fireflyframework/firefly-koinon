# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Browser-owned policy approval and inbound source commands."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.integrations.content_sources.controllers import _actor, _safe, _session
from koinon.integrations.content_sources.mapping_policies import SourcePolicies
from koinon.integrations.content_sources.mapping_service import SourceMappings
from koinon.integrations.content_sources.sync_dtos import (
    SourceControlInput,
    SourceExistingPolicyReviewInput,
    SourceOperationReceipt,
    SourcePolicyApplyInput,
    SourcePolicyReviewInput,
    SourceRunItemPage,
)


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/content-sources")
class SourceMappingController:
    def __init__(self, policies: SourcePolicies, mappings: SourceMappings):
        self.policies, self.mappings = policies, mappings

    @get_mapping("/mappings")
    async def mappings_page(
        self,
        tenant_id: PathVar[str],
        request: Request,
        limit: QueryParam[int] = 25,
        cursor: QueryParam[str | None] = None,
    ) -> dict:
        return await _safe(self.mappings.list(_actor(request), tenant_id, limit=limit, cursor=cursor))

    @get_mapping("/mappings/{mapping_id}")
    async def get(self, tenant_id: PathVar[str], mapping_id: PathVar[str], request: Request) -> dict:
        result = await _safe(self.mappings.get(_actor(request), tenant_id, mapping_id))
        return result.model_dump(mode="json")

    @get_mapping("/mappings/{mapping_id}/runs")
    async def runs(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        request: Request,
        limit: QueryParam[int] = 25,
        cursor: QueryParam[str | None] = None,
    ) -> dict:
        return await _safe(
            self.mappings.runs(_actor(request), tenant_id, mapping_id, limit=limit, cursor=cursor)
        )

    @get_mapping("/operations/{operation_id}")
    async def initial_operation(
        self,
        tenant_id: PathVar[str],
        operation_id: PathVar[str],
        action: QueryParam[str],
        request: Request,
    ) -> SourceOperationReceipt:
        return await _safe(self.mappings.initial_operation(_actor(request), tenant_id, operation_id, action))

    @get_mapping("/mappings/{mapping_id}/operations/{operation_id}")
    async def operation(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        operation_id: PathVar[str],
        action: QueryParam[str],
        request: Request,
    ) -> SourceOperationReceipt:
        return await _safe(
            self.mappings.operation(_actor(request), tenant_id, mapping_id, operation_id, action)
        )

    @get_mapping("/runs/{run_id}")
    async def run(self, tenant_id: PathVar[str], run_id: PathVar[str], request: Request) -> dict:
        result = await _safe(self.mappings.run(_actor(request), tenant_id, run_id))
        return result.model_dump(mode="json")

    @get_mapping("/runs/{run_id}/items")
    async def run_items(
        self,
        tenant_id: PathVar[str],
        run_id: PathVar[str],
        request: Request,
        limit: QueryParam[int] = 25,
        cursor: QueryParam[str | None] = None,
    ) -> SourceRunItemPage:
        return await _safe(
            self.mappings.run_items(_actor(request), tenant_id, run_id, limit=limit, cursor=cursor)
        )

    @post_mapping("/runs/{run_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        run_id: PathVar[str],
        body: Valid[Body[SourceControlInput]],
        request: Request,
    ) -> dict:
        actor = _actor(request)
        mapping = await _safe(self.mappings.run_mapping(actor, tenant_id, run_id))
        return await self._command(tenant_id, mapping, "cancel", body, request, run_id)

    @post_mapping("/runs/{run_id}/retry")
    async def retry(
        self,
        tenant_id: PathVar[str],
        run_id: PathVar[str],
        body: Valid[Body[SourceControlInput]],
        request: Request,
    ) -> dict:
        actor = _actor(request)
        mapping = await _safe(self.mappings.run_mapping(actor, tenant_id, run_id))
        return await self._command(tenant_id, mapping, "retry", body, request, run_id)

    @post_mapping("/mapping-reviews", status_code=201)
    async def review(
        self, tenant_id: PathVar[str], body: Valid[Body[SourcePolicyReviewInput]], request: Request
    ) -> dict:
        result = await _safe(self.policies.review(_actor(request), tenant_id, _session(request), body))
        return result.model_dump(mode="json", by_alias=True)

    @get_mapping("/mapping-reviews/{review_id}/items")
    async def items(
        self,
        tenant_id: PathVar[str],
        review_id: PathVar[str],
        request: Request,
        limit: QueryParam[int] = 25,
        cursor: QueryParam[str | None] = None,
    ) -> dict:
        result = await _safe(
            self.policies.items(
                _actor(request), tenant_id, review_id, limit=limit, cursor=cursor,
                browser_session=_session(request),
            )
        )
        return result.model_dump(mode="json")

    @post_mapping("/mappings", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[SourcePolicyApplyInput]], request: Request
    ) -> dict:
        actor, browser = _actor(request), _session(request)
        mapping = await _safe(self.policies.review_mapping(actor, tenant_id, body.review_id))
        result = await _safe(self.policies.apply(actor, tenant_id, browser, mapping, body))
        return result.model_dump(mode="json", by_alias=True)

    @post_mapping("/mappings/{mapping_id}/reviews", status_code=201)
    async def revise(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        body: Valid[Body[SourceExistingPolicyReviewInput]],
        request: Request,
    ) -> dict:
        result = await _safe(
            self.policies.review(
                _actor(request),
                tenant_id,
                _session(request),
                body,
                mapping_id=mapping_id,
                expected_revision=body.expected_revision,
            )
        )
        return result.model_dump(mode="json", by_alias=True)

    @post_mapping("/mappings/{mapping_id}/apply")
    async def apply(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        body: Valid[Body[SourcePolicyApplyInput]],
        request: Request,
    ) -> dict:
        result = await _safe(
            self.policies.apply(_actor(request), tenant_id, _session(request), mapping_id, body)
        )
        return result.model_dump(mode="json", by_alias=True)

    async def _command(self, tenant, mapping, action, body, request, target=None):
        actor, browser = _actor(request), _session(request)
        await _safe(self.policies.sessions.require(actor, browser))
        result = await _safe(
            self.mappings.execute(actor, tenant, mapping, action, body, target_run_id=target)
        )
        return result.model_dump(mode="json")

    @post_mapping("/mappings/{mapping_id}/sync")
    async def sync(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        body: Valid[Body[SourceControlInput]],
        request: Request,
    ) -> dict:
        return await self._command(tenant_id, mapping_id, "sync", body, request)

    @post_mapping("/mappings/{mapping_id}/pause")
    async def pause(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        body: Valid[Body[SourceControlInput]],
        request: Request,
    ) -> dict:
        return await self._command(tenant_id, mapping_id, "pause", body, request)

    @post_mapping("/mappings/{mapping_id}/resume")
    async def resume(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        body: Valid[Body[SourceControlInput]],
        request: Request,
    ) -> dict:
        return await self._command(tenant_id, mapping_id, "resume", body, request)

    @post_mapping("/mappings/{mapping_id}/retire")
    async def retire(
        self,
        tenant_id: PathVar[str],
        mapping_id: PathVar[str],
        body: Valid[Body[SourceControlInput]],
        request: Request,
    ) -> dict:
        return await self._command(tenant_id, mapping_id, "retire", body, request)
