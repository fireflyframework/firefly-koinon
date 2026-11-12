# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

import httpx
import pytest

from koinon_sdk import KoinonClient
from koinon_sdk.contracts import SearchRequest


@pytest.mark.parametrize("resource", ["shares", "threads"])
@pytest.mark.parametrize("choices", [None, [], [{"provider": "google_drive", "connection_id": "reader"}]])
async def test_saved_browse_preserves_reader_choice_and_unknown_total(resource, choices):
    from koinon_sdk.history_browse import HistoryBrowseInput
    from koinon_sdk.sharing import ShareBrowseInput

    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200, json={"items": [], "next_cursor": "c" * 43, "total": None, "total_is_exact": False}
        )

    value_type = ShareBrowseInput if resource == "shares" else HistoryBrowseInput
    async with KoinonClient(
        "https://brain.invalid/api/v1", token_provider=lambda: "reader", transport=httpx.MockTransport(handle)
    ) as client:
        page = await getattr(client, "browse_" + resource)(
            "north", value_type(cursor="b" * 43, reader_source_connections=choices)
        )
    path = "shares" if resource == "shares" else "chat/threads"
    assert requests[0].url.path == f"/api/v1/tenants/north/{path}/browse"
    assert json.loads(requests[0].content).get("reader_source_connections") == choices
    assert page.total is None and page.total_is_exact is False and page.next_cursor == "c" * 43


@pytest.mark.parametrize("choices", [[], [{"provider": "google_drive", "connection_id": "reader"}]])
async def test_search_sends_explicit_reader_choices(choices):
    value = SearchRequest(question="Question", reader_source_connections=choices)
    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"hits": [], "answer": None})

    async with KoinonClient(
        "https://brain.invalid/api/v1",
        token_provider=lambda: "reader-token",
        transport=httpx.MockTransport(handle),
    ) as client:
        await client.search("north", **value.model_dump(exclude_none=True))
    assert json.loads(requests[0].content)["reader_source_connections"] == choices
    assert requests[0].headers["authorization"] == "Bearer reader-token"
    assert len(requests) == 1


async def test_browse_cursor_preserves_unknown_totals_and_explicit_empty_choice():
    from koinon_sdk import catalog_browse

    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            json={"items": [], "actors": {}, "next_cursor": "b" * 43, "total": None, "total_is_exact": False},
        )

    async with KoinonClient(
        "https://brain.invalid/api/v1",
        token_provider=lambda: "reader-token",
        transport=httpx.MockTransport(handle),
    ) as client:
        page = await client.browse_catalog(
            "north", catalog_browse.CatalogBrowseInput(cursor="a" * 43, reader_source_connections=[])
        )
    assert page.total is None and page.total_is_exact is False
    assert page.next_cursor == "b" * 43
    assert requests[0].method == "POST"
    assert requests[0].url.path == "/api/v1/tenants/north/catalog/browse"
    assert json.loads(requests[0].content)["reader_source_connections"] == []


async def test_reader_preferences_preserve_revision_and_empty_replacement():
    from koinon_sdk.reader_sources import ReaderSelectionInput

    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(200, json={"revision": 2, "connections": []})

    async with KoinonClient(
        "https://brain.invalid/api/v1",
        token_provider=lambda: "reader-token",
        transport=httpx.MockTransport(handle),
    ) as client:
        await client.reader_source_selection("north")
        result = await client.replace_reader_source_selection(
            "north",
            ReaderSelectionInput(
                expected_revision=1, operation_id="21908677-4a5a-4439-9858-1b32a6382c60", connections=[]
            ),
        )
    assert result.revision == 2 and result.connections == ()
    assert requests[0].method == "GET" and requests[1].method == "PUT"
    assert requests[1].url.path == "/api/v1/tenants/north/content-sources/reader-selection"
    assert json.loads(requests[1].content) == {
        "expected_revision": 1,
        "operation_id": "21908677-4a5a-4439-9858-1b32a6382c60",
        "connections": [],
    }


async def test_query_omission_and_explicit_empty_are_distinct():
    requests = []

    def handle(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json={"query_id": "query", "execution_status": "OK"})

    async with KoinonClient(
        "https://brain.invalid/api/v1",
        token_provider=lambda: "reader-token",
        transport=httpx.MockTransport(handle),
    ) as client:
        await client.query("north", "dataset", sql="SELECT 1")
        await client.query("north", "dataset", sql="SELECT 1", reader_source_connections=[])
    assert "reader_source_connections" not in requests[0]
    assert requests[1]["reader_source_connections"] == []


async def test_binary_reader_post_preserves_empty_choices_and_download_headers():
    from koinon_sdk.reader_sources import ReaderReadInput

    requests = []

    def handle(request):
        requests.append(request)
        return httpx.Response(
            200,
            content=b"original",
            headers={
                "Content-Type": "application/pdf",
                "Content-Disposition": 'attachment; filename="source.pdf"',
            },
        )

    async with KoinonClient(
        "https://brain.invalid/api/v1", token_provider=lambda: "reader", transport=httpx.MockTransport(handle)
    ) as client:
        result = await client.read_document_original(
            "north", "doc", ReaderReadInput(reader_source_connections=[])
        )
    assert requests[0].method == "POST" and requests[0].url.path.endswith("/documents/doc/original/read")
    assert json.loads(requests[0].content) == {"reader_source_connections": []}
    assert result.filename == "source.pdf" and result.content == b"original"
