# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import ApiError, KoinonClient


async def test_append_file_uses_one_multipart_file_existing_identity_and_typed_result():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            201,
            json={
                "dataset_id": "data/set",
                "file_version_id": "version",
                "filename": "more.csv",
                "sha256": "a" * 64,
                "byte_size": 3,
                "table_ids": ["table-a", "table-b"],
                "status": "ready",
            },
        )

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        result = await client.append_dataset_file(
            "north", "data/set", filename="more.csv", content=b"x\n2", idempotency_key="stable-request"
        )
    assert result.table_ids == ["table-a", "table-b"] and result.status == "ready"
    assert calls[0].url.raw_path.endswith(b"/datasets/data%2Fset/files")
    assert calls[0].headers["authorization"] == "Bearer fresh"
    assert calls[0].headers["idempotency-key"] == "stable-request"
    assert calls[0].headers["content-type"].startswith("multipart/form-data;")
    assert calls[0].content.count(b'Content-Disposition: form-data; name="file"') == 1
    assert b'filename="more.csv"' in calls[0].content and b"x\n2" in calls[0].content


async def test_unfinished_dataset_conflict_never_automatically_replays_file():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(409, json={"detail": "Reconcile intake", "code": "DATASET_NOT_READY"})

    async with KoinonClient(
        "https://koinon.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ApiError) as error:
            await client.append_dataset_file(
                "north", "dataset", filename="more.csv", content=b"x\n2", idempotency_key="stable-request"
            )
    assert error.value.code == "DATASET_NOT_READY" and len(calls) == 1
