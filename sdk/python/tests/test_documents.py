# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import ApiError, KoinonClient


@pytest.mark.parametrize(
    "body,code,message,reference",
    [
        (
            {"title": "Forbidden", "detail": "Scope denied", "code": "DENIED", "transactionId": "native-123"},
            "DENIED",
            "Scope denied",
            "native-123",
        ),
        (
            {"error": {"code": "NOT_FOUND", "message": "Missing asset", "transaction_id": "legacy-456"}},
            "NOT_FOUND",
            "Missing asset",
            "legacy-456",
        ),
    ],
)
async def test_native_and_legacy_error_references(body, code, message, reference):
    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "caller",
        transport=httpx.MockTransport(lambda r: httpx.Response(403, json=body)),
    ) as client:
        with pytest.raises(ApiError) as raised:
            await client.context()
    assert raised.value.code == code
    assert str(raised.value) == message
    assert raised.value.request_id == reference
    assert raised.value.transaction_id == reference


async def test_document_filters_string_section_and_authenticated_binary_download():
    seen = []
    tokens = iter(["chunks-token", "original-token"])

    def handle(request):
        seen.append(request)
        if request.url.path.endswith("/original"):
            return httpx.Response(200, content=b"\x00binary\xff", headers={"content-type": "application/pdf"})
        return httpx.Response(
            200,
            json={
                "document_id": "d/1",
                "source_id": "s",
                "native_source_id": "n",
                "items": [
                    {
                        "id": "c",
                        "index": 2,
                        "total_chunks": 5,
                        "text": "Evidence",
                        "char_start": 10,
                        "char_end": 18,
                        "page": 3,
                        "section_path": "Part A / Finding",
                        "embedding_model": None,
                    }
                ],
                "offset": 2,
                "limit": 10,
                "total": 5,
                "next_offset": None,
            },
        )

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: next(tokens),
        transport=httpx.MockTransport(handle),
    ) as client:
        page = await client.document_chunks(
            "t/1", "d/1", offset=2, limit=10, page=3, section="Part A", q="evidence"
        )
        original = await client.document_original("t/1", "d/1")
    assert page.items[0].section_path == "Part A / Finding"
    assert original == b"\x00binary\xff"
    assert seen[0].url.raw_path.startswith(b"/api/v1/tenants/t%2F1/documents/d%2F1/chunks?")
    assert dict(seen[0].url.params) == {
        "offset": "2",
        "limit": "10",
        "page": "3",
        "section": "Part A",
        "q": "evidence",
    }
    assert [r.headers["authorization"] for r in seen] == ["Bearer chunks-token", "Bearer original-token"]


def test_operator_unknown_survives_typed_sdk_configuration():
    from koinon_sdk import DeploymentConfiguration

    status = {
        "configured": True,
        "available": None,
        "status": "unknown",
        "observed_at": "now",
        "reason": "Unverified",
    }
    configuration = DeploymentConfiguration.model_validate(
        {
            "ownership": "deployment",
            "read_only": True,
            "datasources": [],
            "storage": [],
            "indexes": [dict(status, id="document-vectors")],
            "metrics": status,
            "limits": {
                "worker_concurrency": 1,
                "max_queued_per_subject": 50,
                "job_lease_seconds": 60,
                "max_index_workspaces": 32,
            },
        }
    )
    assert configuration.indexes[0].available is None and configuration.read_only is True
