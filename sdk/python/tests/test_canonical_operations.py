# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest

from koinon_sdk import KnowledgeConnectionInput, KoinonClient, MemberInput, MemberUpdate


async def test_content_preconditions_multipart_and_exact_data_are_preserved():
    seen = []
    entry = {
        "id": "a",
        "tenant_id": "t",
        "kind": "document",
        "name": "a",
        "status": "ready",
        "created_at": "2026-10-27T00:00:00Z",
    }

    def handle(request):
        seen.append(request)
        return httpx.Response(
            201,
            json={
                "asset": entry,
                "source": entry,
                "version": entry,
                "effects": {"amount": "9007199254740993"},
            },
        )

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        result = await client.replace_document(
            "t",
            "a",
            filename="x.txt",
            content=b"replacement",
            expected_sha256="abc",
            acknowledge_chunk_invalidation=True,
        )
        await client.reingest_document("t", "a", expected_sha256="abc", acknowledge_chunk_invalidation=True)
    assert result.effects.model_dump()["amount"] == "9007199254740993"
    assert seen[0].headers["if-match"] == '"abc"'
    assert "multipart/form-data; boundary=" in seen[0].headers["content-type"]
    assert b"replacement" in seen[0].content and b"true" in seen[0].content
    assert json.loads(seen[1].content) == {"acknowledge_chunk_invalidation": True}


async def test_download_retains_etag_and_authorized_not_modified():
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(
            304 if len(seen) == 2 else 200,
            content=b"" if len(seen) == 2 else b"original",
            headers={
                "ETag": '"digest"',
                "Content-Type": "text/plain",
                "Content-Disposition": "attachment; filename*=UTF-8''evidence%20one.txt",
            },
        )

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        result = await client.document_download("t", "doc/one")
        cached = await client.person_avatar("t", "person/one", workspace_id="w", if_none_match='"digest"')
    assert result.content == b"original" and result.etag == '"digest"'
    assert result.filename == "evidence one.txt"
    assert cached.not_modified and cached.content == b""
    assert seen[1].headers["authorization"] == "Bearer fresh"
    assert seen[1].headers["if-none-match"] == '"digest"'
    assert seen[1].url.params["workspace_id"] == "w"


@pytest.mark.parametrize(
    "method",
    [
        "add_member",
        "update_member",
        "remove_member",
        "delete",
        "job",
        "cancel_job",
        "knowledge_roles",
        "knowledge_connections",
        "create_knowledge_connection",
        "update_knowledge_connection",
        "delete_knowledge_connection",
        "replace_table",
        "reingest_table",
    ],
)
def test_all_canonical_operation_helpers_exist(method):
    assert callable(getattr(KoinonClient, method, None))


async def test_membership_binding_and_pagination_wire_contracts():
    seen = []
    member = {"id": "m", "tenant_id": "t", "subject": "issuer|subject", "role": "viewer", "active": True}
    connection = {
        "id": "c",
        "tenant_id": "t",
        "domain": "documents",
        "role": "documents.answer",
        "mode": "current_agent",
        "model_options": {},
        "enabled": True,
        "revision": 2,
        "created_by": "issuer|subject",
        "updated_by": "issuer|subject",
        "created_at": "2026-10-27T00:00:00Z",
        "updated_at": "2026-10-27T00:00:00Z",
    }

    def handle(request):
        seen.append(request)
        if request.method == "DELETE":
            return (
                httpx.Response(200, json={"deleted": True})
                if "knowledge-connections" in request.url.path
                else httpx.Response(204)
            )
        if request.url.path.endswith("/agents"):
            return httpx.Response(200, json={"items": [], "page": 2, "page_size": 1, "total": 3})
        return httpx.Response(200, json=connection if "knowledge-connections" in request.url.path else member)

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        await client.add_member("t", MemberInput(subject="issuer|subject", role="viewer", workspace_id=None))
        await client.update_member("t", "m/one", MemberUpdate(active=False))
        await client.update_knowledge_connection(
            "t",
            "c/one",
            KnowledgeConnectionInput(
                domain="documents",
                role="documents.answer",
                mode="current_agent",
                workspace_id=None,
                expected_revision=1,
            ),
        )
        await client.delete_knowledge_connection("t", "c/one", expected_revision=2)
        page = await client.agents("t", page=2, page_size=1, status="unverified")
    assert json.loads(seen[0].content)["workspace_id"] is None
    assert json.loads(seen[1].content) == {"active": False}
    assert json.loads(seen[2].content)["workspace_id"] is None
    assert seen[3].url.params["expected_revision"] == "2"
    assert page.page == 2 and page.page_size == 1 and page.total == 3
    assert all(request.headers["authorization"] == "Bearer fresh" for request in seen)


async def test_opaque_query_precision_and_false_filter_values_survive():
    seen = []

    def handle(request):
        seen.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"items": []})
        return httpx.Response(
            200,
            json={
                "query_id": "q",
                "execution_status": "OK",
                "preview": [
                    {
                        "positive": "9007199254740993",
                        "negative": "-9007199254740993",
                        "decimal": "-0.1234567890123456789",
                        "safe": 9007199254740991,
                        "flag": False,
                        "nested": [None, "18446744073709551615"],
                    }
                ],
            },
        )

    async with KoinonClient(
        "https://example.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        await client.catalog("t", include_archived=False, page=2, page_size=10)
        result = await client.query("t", "dataset", sql="SELECT 1")
    assert seen[0].url.params["include_archived"] == "false"
    assert result.preview[0]["positive"] == "9007199254740993"
    assert result.preview[0]["negative"] == "-9007199254740993"
    assert result.preview[0]["decimal"] == "-0.1234567890123456789"
    assert result.preview[0]["flag"] is False
    assert result.preview[0]["safe"] == 9007199254740991


def test_all_canonical_operations_have_typed_public_helpers():
    import inspect
    from pathlib import Path

    contract = json.loads((Path(__file__).resolve().parents[3] / "sdk/contract/operations.json").read_text())
    assert contract["canonical_operation_count"] == len(contract["operations"])
    for operation in contract["operations"]:
        method = getattr(KoinonClient, operation["sdk_python"])
        signature = inspect.signature(method)
        assert signature.return_annotation is not inspect.Signature.empty, operation["operation"]
        for parameter in signature.parameters.values():
            if parameter.name != "self":
                assert parameter.annotation is not inspect.Parameter.empty
                assert "Any" not in str(parameter.annotation), operation["operation"]
