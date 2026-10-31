# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import ApiError, KoinonClient
from koinon_sdk.bulk_queries import QueryBatchAction, QueryBatchCreate


async def test_eight_query_operations_keep_scope_keys_current_credentials_and_distinct_cancellation():
    calls = []
    batch = {
        "id": "batch",
        "tenant_id": "north",
        "workspace_id": "workspace",
        "status": "queued",
        "revision": 7,
        "total_items": 1,
        "counts": {"queued": 1},
        "cancellation_requested": False,
        "created_at": "2026-10-30T00:00:00Z",
        "expires_at": "2026-10-31T00:00:00Z",
    }

    def handle(request):
        calls.append(request)
        path = request.url.path
        value = batch
        if path.endswith("capabilities"):
            value = {"configured": True}
        elif path.endswith("/result"):
            value = {"batch_id": "batch", "item_id": "item", "status": "reconciling"}
        elif path.endswith("/cancel"):
            value = {"batch_id": "batch", "revision": 8, "cancellation_requested": True}
        elif request.method == "GET" and path.endswith(("/batches", "/items")):
            value = {"items": [], "total": 0, "page": 2, "page_size": 3, "pages": 0}
        return httpx.Response(200, json=value)

    tokens = []

    def token():
        value = "current-" + str(len(tokens))
        tokens.append(value)
        return value

    async with KoinonClient(
        "https://inert.test/api/v1", token_provider=token, transport=httpx.MockTransport(handle)
    ) as client:
        await client.query_batch_capabilities("north/office", "workspace")
        await client.create_query_batch(
            "north/office",
            QueryBatchCreate.model_validate(
                {
                    "workspace_id": "workspace",
                    "items": [{"client_item_id": "one", "dataset_id": "dataset", "question": "Count"}],
                }
            ),
            "create-key",
        )
        await client.query_batches("north/office", page=2, page_size=3)
        await client.query_batch("north/office", "batch/one")
        await client.query_batch_items("north/office", "batch/one", page=2, page_size=3)
        result = await client.query_batch_result("north/office", "batch/one", "item/one")
        assert result.status == "reconciling" and result.result is None
        cancelled = await client.cancel_query_batch(
            "north/office", "batch/one", QueryBatchAction(expected_revision=7), "cancel-key"
        )
        assert cancelled.cancellation_requested and cancelled.revision == 8
        await client.reconcile_query_batch_item(
            "south", "batch/one", "item/one", QueryBatchAction(expected_revision=8), "inspect-key"
        )
    assert len(calls) == len(tokens) == 8
    assert b"north%2Foffice/queries/batches/batch%2Fone/items/item%2Fone/result" in calls[5].url.raw_path
    assert calls[7].headers["Idempotency-Key"] == "inspect-key"
    assert calls[7].content == b'{"expected_revision":8}'
    assert calls[7].url.path.startswith("/api/v1/tenants/south/")
    assert [request.headers["Authorization"] for request in calls] == ["Bearer " + value for value in tokens]


async def test_unknown_query_admission_is_one_dispatch_and_does_not_replay_models():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(503, json={"code": "BULK_QUERY_OUTCOME_UNRESOLVED"})

    async with KoinonClient(
        "https://inert.test/api/v1", token_provider=lambda: "token", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ApiError):
            await client.reconcile_query_batch_item(
                "north", "batch", "item", QueryBatchAction(expected_revision=1), "stable"
            )
    assert len(calls) == 1
