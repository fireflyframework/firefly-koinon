# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import ApiError, KoinonClient
from koinon_sdk.bulk import BulkAction, BulkDestination, FileBatchCreate, FileManifestItem


async def test_all_batch_operations_keep_explicit_scope_keys_revisions_and_raw_original_bytes():
    requests = []
    batch = {
        "id": "batch",
        "tenant_id": "north",
        "destination": {"workspace_id": "w", "project_id": "p", "parent_id": "c"},
        "status": "staging",
        "revision": 1,
        "total_items": 1,
        "total_bytes": 8,
        "counts": {},
        "cancellation_requested": False,
        "created_at": "2026-10-30T00:00:00Z",
        "expires_at": "2026-10-31T00:00:00Z",
    }
    receipt = {
        "receipt_id": "receipt",
        "batch_id": "batch",
        "item_id": "item",
        "sha256": "a" * 64,
        "size_bytes": 8,
    }

    def handle(request):
        requests.append(request)
        path = request.url.path
        if path.endswith("capabilities"):
            value = {
                "configured": True,
                "modes": ["document", "dataset"],
                "max_files": 100,
                "max_file_bytes": 33554432,
                "max_batch_bytes": 268435456,
                "max_active_batches_per_subject": 2,
            }
        elif path.endswith(("/content", "/receipt")):
            value = receipt
        elif request.method == "GET" and (path.endswith("/batches") or path.endswith("/items")):
            value = {"items": [], "total": 0, "page": 2, "page_size": 3, "pages": 0}
        else:
            value = batch
        return httpx.Response(200, json=value)

    tokens = []

    def token():
        tokens.append(1)
        return "current-token"

    async with KoinonClient(
        "https://inert.test/api/v1", token_provider=token, transport=httpx.MockTransport(handle)
    ) as client:
        capabilities = await client.file_batch_capabilities("north/office", "w")
        assert capabilities.staging_topology == "single_host_shared_durable_posix"
        manifest = FileBatchCreate(
            destination=BulkDestination(workspace_id="w", project_id="p", parent_id="c"),
            items=[
                FileManifestItem(
                    client_item_id="one", filename="facts.csv", mode="dataset", size_bytes=8, sha256="a" * 64
                )
            ],
        )
        await client.create_file_batch("north/office", manifest, "create-key")
        await client.file_batches("north/office", page=2, page_size=3)
        await client.file_batch("north/office", "batch/one")
        await client.file_batch_items("north/office", "batch/one", page=2, page_size=3)
        await client.upload_file_batch_item(
            "north/office", "batch/one", "item/one", b"original", "upload-key"
        )
        await client.file_batch_item_receipt("north/office", "batch/one", "item/one")
        action = BulkAction(expected_revision=7)
        await client.submit_file_batch("north/office", "batch/one", action, "submit-key")
        await client.cancel_file_batch("north/office", "batch/one", action, "cancel-key")
        await client.reconcile_file_batch_item("north/office", "batch/one", "item/one", action, "inspect-key")
        await client.reconcile_file_batch_original("south", "batch/one", "item/one", action, "original-key")
    assert len(requests) == len(tokens) == 11
    assert all(r.headers["authorization"] == "Bearer current-token" for r in requests)
    raw = requests[5]
    assert raw.content == b"original" and raw.headers["content-type"] == "application/octet-stream"
    assert raw.headers["idempotency-key"] == "upload-key"
    assert b"north%2Foffice/sources/batches/batch%2Fone/items/item%2Fone/content" in raw.url.raw_path
    assert requests[-1].url.path.startswith("/api/v1/tenants/south/")
    assert requests[-1].content == b'{"expected_revision":7}'


async def test_uncertain_batch_mutation_is_sent_once_and_error_metadata_survives():
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            503,
            json={
                "code": "BULK_NATIVE_OUTCOME_UNRESOLVED",
                "detail": "Inspect retained receipt",
                "request_id": "request",
            },
        )

    async with KoinonClient(
        "https://inert.test/api/v1", token_provider=lambda: "token", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ApiError) as failure:
            await client.submit_file_batch("north", "batch", BulkAction(expected_revision=2), "stable-key")
    assert len(requests) == 1 and failure.value.code == "BULK_NATIVE_OUTCOME_UNRESOLVED"
    assert failure.value.request_id == "request"
