# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.knowledge.indexes.activation import IndexActivation
from koinon.knowledge.indexes.dtos import (
    IndexActivateInput,
    IndexCreateInput,
    IndexJobView,
    IndexPage,
    IndexPlanInput,
    IndexPlanView,
    IndexRevisionInput,
    KnowledgeIndexView,
    NativeIndexChoice,
    NativeIndexPage,
)
from koinon.knowledge.indexes.lifecycle import IndexLifecycleService
from koinon.knowledge.indexes.service import KnowledgeIndexService
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.indexes_controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class KnowledgeIndexesController:
    def __init__(
        self, indexes: KnowledgeIndexService, lifecycle: IndexLifecycleService, activation: IndexActivation
    ):
        self.indexes, self.lifecycle, self.activation = indexes, lifecycle, activation

    @get_mapping("/knowledge-indexes")
    async def list_indexes(
        self,
        tenant_id: PathVar[str],
        workspace_id: QueryParam[str],
        domain: QueryParam[str],
        request: Request,
        limit: QueryParam[int] = 50,
        offset: QueryParam[int] = 0,
        status: QueryParam[str | None] = None,
        dimensions: QueryParam[int | None] = None,
        model_id: QueryParam[str | None] = None,
        provider_kind: QueryParam[str | None] = None,
    ) -> IndexPage:
        return IndexPage.model_validate(
            await self.indexes.list(
                identity_from_request(request).subject,
                tenant_id,
                workspace_id=workspace_id,
                domain=domain,
                limit=limit,
                offset=offset,
                status=status,
                dimensions=dimensions,
                model_id=model_id,
                provider_kind=provider_kind,
            )
        )

    @get_mapping("/knowledge-index-choices")
    async def choices(
        self,
        tenant_id: PathVar[str],
        workspace_id: QueryParam[str],
        domain: QueryParam[str],
        request: Request,
        limit: QueryParam[int] = 50,
        offset: QueryParam[int] = 0,
        status: QueryParam[str | None] = None,
        dimensions: QueryParam[int | None] = None,
        model_id: QueryParam[str | None] = None,
        provider_kind: QueryParam[str | None] = None,
    ) -> NativeIndexPage:
        return NativeIndexPage.model_validate(
            await self.indexes.choices(
                identity_from_request(request).subject,
                tenant_id,
                workspace_id=workspace_id,
                domain=domain,
                limit=limit,
                offset=offset,
                status=status,
                dimensions=dimensions,
                model_id=model_id,
                provider_kind=provider_kind,
            )
        )

    @get_mapping("/knowledge-index-choices/{choice_id}")
    async def choice(
        self,
        tenant_id: PathVar[str],
        choice_id: PathVar[str],
        workspace_id: QueryParam[str],
        domain: QueryParam[str],
        request: Request,
    ) -> NativeIndexChoice:
        return NativeIndexChoice.model_validate(
            await self.indexes.choice(
                identity_from_request(request).subject,
                tenant_id,
                choice_id,
                workspace_id=workspace_id,
                domain=domain,
            )
        )

    @get_mapping("/knowledge-indexes/{index_id}")
    async def get(
        self, tenant_id: PathVar[str], index_id: PathVar[str], request: Request
    ) -> KnowledgeIndexView:
        return KnowledgeIndexView.model_validate(
            await self.lifecycle.get(identity_from_request(request).subject, tenant_id, index_id)
        )

    @post_mapping("/knowledge-indexes/plan")
    async def plan(
        self, tenant_id: PathVar[str], body: Valid[Body[IndexPlanInput]], request: Request
    ) -> IndexPlanView:
        return IndexPlanView.model_validate(
            await self.indexes.plan(identity_from_request(request).subject, tenant_id, body.model_dump())
        )

    @post_mapping("/knowledge-indexes", status_code=202)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[IndexCreateInput]], request: Request
    ) -> IndexJobView:
        return IndexJobView.model_validate(
            await self.lifecycle.create(
                identity_from_request(request).subject,
                tenant_id,
                body.model_dump(),
                request.headers.get("Idempotency-Key", ""),
            )
        )

    @post_mapping("/knowledge-indexes/{index_id}/activate")
    async def activate(
        self,
        tenant_id: PathVar[str],
        index_id: PathVar[str],
        body: Valid[Body[IndexActivateInput]],
        request: Request,
    ) -> KnowledgeIndexView:
        return KnowledgeIndexView.model_validate(
            await self.activation.activate(
                identity_from_request(request).subject, tenant_id, index_id, body.model_dump()
            )
        )

    @post_mapping("/knowledge-indexes/{index_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        index_id: PathVar[str],
        body: Valid[Body[IndexRevisionInput]],
        request: Request,
    ) -> KnowledgeIndexView:
        return KnowledgeIndexView.model_validate(
            await self.lifecycle.cancel(
                identity_from_request(request).subject, tenant_id, index_id, body.expected_revision
            )
        )

    @post_mapping("/knowledge-indexes/{index_id}/resume", status_code=202)
    async def resume(
        self,
        tenant_id: PathVar[str],
        index_id: PathVar[str],
        body: Valid[Body[IndexRevisionInput]],
        request: Request,
    ) -> IndexJobView:
        return IndexJobView.model_validate(
            await self.lifecycle.resume(
                identity_from_request(request).subject,
                tenant_id,
                index_id,
                body.expected_revision,
                request.headers.get("Idempotency-Key", ""),
            )
        )
