# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent durable queries; mutations require explicit keys and are not retried."""

from abc import ABC, abstractmethod
from typing import Any
from urllib.parse import quote

from koinon_sdk.bulk_queries import (
    QueryBatchAction,
    QueryBatchCancellation,
    QueryBatchCapabilities,
    QueryBatchCreate,
    QueryBatchItemPage,
    QueryBatchPage,
    QueryBatchResult,
    QueryBatchView,
)


class QueryBatchClientMixin(ABC):
    @staticmethod
    @abstractmethod
    def _tenant(tenant_id: str) -> str:
        raise NotImplementedError

    @abstractmethod
    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        raise NotImplementedError

    def _query_batch_path(self, tenant_id: str, batch_id: str) -> str:
        return self._tenant(tenant_id) + "/queries/batches/" + quote(batch_id, safe="")

    async def query_batch_capabilities(self, tenant_id: str, workspace_id: str) -> QueryBatchCapabilities:
        return QueryBatchCapabilities.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/query-batch-capabilities",
                params={"workspace_id": workspace_id},
            )
        )

    async def create_query_batch(
        self, tenant_id: str, value: QueryBatchCreate, idempotency_key: str
    ) -> QueryBatchView:
        return QueryBatchView.model_validate(
            await self._request(
                "POST",
                self._tenant(tenant_id) + "/queries/batches",
                json=value.model_dump(mode="json", exclude_unset=True),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def query_batches(self, tenant_id: str, *, page: int = 1, page_size: int = 25) -> QueryBatchPage:
        return QueryBatchPage.model_validate(
            await self._request(
                "GET",
                self._tenant(tenant_id) + "/queries/batches",
                params={"page": page, "page_size": page_size},
            )
        )

    async def query_batch(self, tenant_id: str, batch_id: str) -> QueryBatchView:
        return QueryBatchView.model_validate(
            await self._request("GET", self._query_batch_path(tenant_id, batch_id))
        )

    async def query_batch_items(
        self, tenant_id: str, batch_id: str, *, page: int = 1, page_size: int = 25
    ) -> QueryBatchItemPage:
        return QueryBatchItemPage.model_validate(
            await self._request(
                "GET",
                self._query_batch_path(tenant_id, batch_id) + "/items",
                params={"page": page, "page_size": page_size},
            )
        )

    async def query_batch_result(self, tenant_id: str, batch_id: str, item_id: str) -> QueryBatchResult:
        return QueryBatchResult.model_validate(
            await self._request(
                "GET",
                self._query_batch_path(tenant_id, batch_id) + "/items/" + quote(item_id, safe="") + "/result",
            )
        )

    async def cancel_query_batch(
        self, tenant_id: str, batch_id: str, value: QueryBatchAction, idempotency_key: str
    ) -> QueryBatchCancellation:
        return QueryBatchCancellation.model_validate(
            await self._request(
                "POST",
                self._query_batch_path(tenant_id, batch_id) + "/cancel",
                json=value.model_dump(mode="json"),
                headers={"Idempotency-Key": idempotency_key},
            )
        )

    async def reconcile_query_batch_item(
        self, tenant_id: str, batch_id: str, item_id: str, value: QueryBatchAction, idempotency_key: str
    ) -> QueryBatchView:
        return QueryBatchView.model_validate(
            await self._request(
                "POST",
                self._query_batch_path(tenant_id, batch_id)
                + "/items/"
                + quote(item_id, safe="")
                + "/reconcile",
                json=value.model_dump(mode="json"),
                headers={"Idempotency-Key": idempotency_key},
            )
        )
