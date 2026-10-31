# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.knowledge.bulk.controllers import action_key
from koinon.knowledge.bulk_queries.dtos import (
    QueryBatchAction,
    QueryBatchCancellation,
    QueryBatchCapabilities,
    QueryBatchCreate,
    QueryBatchItemPage,
    QueryBatchPage,
    QueryBatchResult,
    QueryBatchView,
)
from koinon.knowledge.bulk_queries.service import QueryBatches
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.bulk_queries.controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class QueryBatchController:
    def __init__(self, queries: QueryBatches):
        self.queries = queries

    @get_mapping("/query-batch-capabilities")
    async def capabilities(
        self, tenant_id: PathVar[str], request: Request, workspace_id: QueryParam[str]
    ) -> QueryBatchCapabilities:
        return await self.queries.capabilities(
            identity_from_request(request).subject, tenant_id, workspace_id
        )

    @post_mapping("/queries/batches", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[QueryBatchCreate]], request: Request
    ) -> QueryBatchView:
        return await self.queries.create(
            identity_from_request(request).subject, tenant_id, body, action_key(request)
        )

    @get_mapping("/queries/batches")
    async def list(
        self,
        tenant_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> QueryBatchPage:
        return await self.queries.list(
            identity_from_request(request).subject, tenant_id, page=page, page_size=page_size
        )

    @get_mapping("/queries/batches/{batch_id}")
    async def get(self, tenant_id: PathVar[str], batch_id: PathVar[str], request: Request) -> QueryBatchView:
        return await self.queries.get(identity_from_request(request).subject, tenant_id, batch_id)

    @get_mapping("/queries/batches/{batch_id}/items")
    async def items(
        self,
        tenant_id: PathVar[str],
        batch_id: PathVar[str],
        request: Request,
        page: QueryParam[int] = 1,
        page_size: QueryParam[int] = 25,
    ) -> QueryBatchItemPage:
        return await self.queries.items(
            identity_from_request(request).subject, tenant_id, batch_id, page=page, page_size=page_size
        )

    @get_mapping("/queries/batches/{batch_id}/items/{item_id}/result")
    async def result(
        self, tenant_id: PathVar[str], batch_id: PathVar[str], item_id: PathVar[str], request: Request
    ) -> QueryBatchResult:
        return await self.queries.result(identity_from_request(request).subject, tenant_id, batch_id, item_id)

    @post_mapping("/queries/batches/{batch_id}/cancel")
    async def cancel(
        self,
        tenant_id: PathVar[str],
        batch_id: PathVar[str],
        body: Valid[Body[QueryBatchAction]],
        request: Request,
    ) -> QueryBatchCancellation:
        return await self.queries.cancel(
            identity_from_request(request).subject, tenant_id, batch_id, body, action_key(request)
        )

    @post_mapping("/queries/batches/{batch_id}/items/{item_id}/reconcile")
    async def reconcile(
        self,
        tenant_id: PathVar[str],
        batch_id: PathVar[str],
        item_id: PathVar[str],
        body: Valid[Body[QueryBatchAction]],
        request: Request,
    ) -> QueryBatchView:
        return await self.queries.reconcile(
            identity_from_request(request).subject, tenant_id, batch_id, item_id, body, action_key(request)
        )
