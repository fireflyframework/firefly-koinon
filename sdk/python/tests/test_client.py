# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import httpx
import pytest

from koinon_sdk import ApiError, KoinonClient


async def test_scope_encoding_and_fresh_caller_tokens():
    tokens = iter(["first", "renewed"])
    seen = []

    def handle(request):
        seen.append((request.url.raw_path, request.headers["authorization"]))
        return httpx.Response(200, json={"items": []})

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: next(tokens),
        transport=httpx.MockTransport(handle),
    ) as client:
        await client.catalog("north/division", kind="document")
        await client.catalog("north/division", kind="document")
    assert seen == [
        (b"/api/v1/tenants/north%2Fdivision/catalog?kind=document", "Bearer first"),
        (b"/api/v1/tenants/north%2Fdivision/catalog?kind=document", "Bearer renewed"),
    ]


async def test_problem_details_preserved_without_automatic_retry():
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(
            403,
            json={
                "title": "Forbidden",
                "detail": "Membership required",
                "code": "ACCESS_DENIED",
                "request_id": "trace-1",
            },
        )

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "scoped",
        transport=httpx.MockTransport(handle),
    ) as client:
        with pytest.raises(ApiError) as raised:
            await client.context()
        assert raised.value.status == 403
        assert raised.value.code == "ACCESS_DENIED"
        assert raised.value.request_id == "trace-1"
    assert len(calls) == 1


async def test_missing_token_fails_before_transport():
    def handle(request):
        pytest.fail("Unauthenticated transport must not be invoked")

    async with KoinonClient(
        "https://knowledge.test/api/v1", token_provider=lambda: "", transport=httpx.MockTransport(handle)
    ) as client:
        with pytest.raises(ValueError, match="bearer token"):
            await client.context()


ENTRY = {
    "id": "asset-1",
    "tenant_id": "north",
    "kind": "document",
    "name": "Evidence",
    "status": "ready",
    "created_at": "2026-10-26T00:00:00Z",
}


@pytest.mark.parametrize(
    "operation,args,kwargs,method,suffix,response",
    [
        ("get", ("north", "asset-1"), {}, "GET", "/catalog/asset-1", ENTRY),
        (
            "create",
            ("north",),
            {"kind": "document", "name": "Evidence", "parent_id": "source-1"},
            "POST",
            "/catalog",
            ENTRY,
        ),
        ("update", ("north", "asset-1"), {"name": "Revised"}, "PATCH", "/catalog/asset-1", ENTRY),
        ("archive", ("north", "asset-1"), {}, "POST", "/catalog/asset-1/archive", ENTRY),
        ("restore", ("north", "asset-1"), {}, "POST", "/catalog/asset-1/restore", ENTRY),
        ("search", ("north", "Which evidence?"), {}, "POST", "/search", {"hits": [], "citations": []}),
        (
            "query",
            ("north", "dataset-1", "Total?"),
            {},
            "POST",
            "/query",
            {"query_id": "query-1", "execution_status": "REJECTED_BY_FIREWALL"},
        ),
        ("capabilities", (), {}, "GET", "/capabilities", {"providers": [], "features": []}),
        ("schema", ("north", "dataset-1"), {}, "GET", "/datasets/dataset-1/schema", {"tables": []}),
        ("lineage", ("north",), {}, "GET", "/lineage", {"nodes": [], "edges": []}),
        ("audit", ("north",), {}, "GET", "/audit", {"items": []}),
        ("members", ("north",), {}, "GET", "/members", {"items": []}),
        ("jobs", ("north",), {}, "GET", "/jobs", {"items": []}),
    ],
)
async def test_unified_operation_contract(operation, args, kwargs, method, suffix, response):
    seen = []

    def handle(request):
        seen.append(request)
        assert request.method == method
        assert request.url.path.endswith(suffix)
        assert request.headers["authorization"] == "Bearer scoped"
        return httpx.Response(204) if response is None else httpx.Response(200, json=response)

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "scoped",
        transport=httpx.MockTransport(handle),
    ) as client:
        result = await getattr(client, operation)(*args, **kwargs)
        if operation == "query":
            assert result.execution_status == "REJECTED_BY_FIREWALL"
    assert len(seen) == 1


async def test_upload_keeps_binary_multipart_contract():
    def handle(request):
        assert request.url.path.endswith("/sources/upload")
        assert request.headers["content-type"].startswith("multipart/form-data; boundary=")
        assert b"hello from an owned fixture" in request.content
        assert b'filename="evidence.txt"' in request.content
        return httpx.Response(200, json={"source": ENTRY, "assets": [ENTRY]})

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "scoped",
        transport=httpx.MockTransport(handle),
    ) as client:
        result = await client.upload(
            "north",
            filename="evidence.txt",
            content=b"hello from an owned fixture",
            parent_id="collection-1",
            workspace_id="workspace-1",
            project_id="project-1",
            mode="document",
        )
        assert result.source.id == "asset-1"


async def test_archive_filter_is_explicit_and_pipeline_status_is_not_mutable():
    calls = []

    def handle(request):
        calls.append(request)
        assert request.url.params["include_archived"] == "true"
        return httpx.Response(200, json={"items": []})

    async with KoinonClient(
        "https://api.test/api/v1", token_provider=lambda: "fresh", transport=httpx.MockTransport(handle)
    ) as client:
        await client.catalog("north", include_archived=True)
        with pytest.raises(TypeError):
            await client.update("north", "asset-1", status="ready")
    assert len(calls) == 1


async def test_catalog_filters_preserve_typed_summaries_and_unknown_counts():
    def handle(request):
        assert request.url.params["tag"] == "reviewed"
        assert request.url.params["format"] == "pdf"
        assert request.url.params["sort"] == "kind"
        return httpx.Response(
            200,
            json={
                "items": [ENTRY],
                "summaries": {
                    "asset-1": {
                        "format": "pdf",
                        "tags": ["pdf", "reviewed"],
                        "size_bytes": 12,
                        "row_count": None,
                    }
                },
            },
        )

    async with KoinonClient(
        "https://knowledge.test/api/v1",
        token_provider=lambda: "scoped",
        transport=httpx.MockTransport(handle),
    ) as client:
        page = await client.catalog("north", tag="reviewed", format="pdf", sort="kind")
    assert page.summaries["asset-1"].format == "pdf"
    assert page.summaries["asset-1"].row_count is None
    assert page.summaries["asset-1"].size_bytes == 12


async def test_folder_move_sends_exact_observed_preconditions_and_preserves_protection():
    import json

    from koinon_sdk import CatalogMove

    def handle(request):
        assert request.method == "POST"
        assert request.url.raw_path == b"/api/v1/tenants/north%2Fdivision/catalog/folder%2Fone/move"
        body = json.loads(request.content)
        assert body == {
            "parent_id": "destination", "expected_parent_id": "original",
            "expected_updated_at": "2026-11-01T08:00:00Z",
        }
        return httpx.Response(200, json={**ENTRY, "system_managed": False})

    async with KoinonClient(
        "https://knowledge.test/api/v1", token_provider=lambda: "editor",
        transport=httpx.MockTransport(handle),
    ) as client:
        moved = await client.move("north/division", "folder/one", CatalogMove(
            parent_id="destination", expected_parent_id="original",
            expected_updated_at="2026-11-01T08:00:00Z",
        ))
    assert moved.system_managed is False
