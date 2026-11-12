# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader choices survive the real MCP-to-canonical transport boundary."""

import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from test_mcp_server import protocol, settings

from koinon.mcp.server import create_mcp_server


@pytest.mark.parametrize(
    "selection", [None, [], [{"provider": "google_drive", "connection_id": "reader-account"}]]
)
async def test_search_preserves_reader_selection_without_forwarding_credentials(selection):
    requests = []

    async def canonical(request):
        requests.append((await request.json(), dict(request.headers)))
        return JSONResponse({"hits": [], "answer": None})

    server = create_mcp_server(
        Starlette(routes=[Route("/api/v1/tenants/north/search", canonical, methods=["POST"])]), settings()
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    arguments = {"tenant_id": "north", "question": "Allowed knowledge"}
    if selection is not None:
        arguments["reader_source_connections"] = selection
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer reader-token", "Cookie": "session=private"}) as session,
    ):
        result = await session.call_tool("koinon_search", arguments)
    assert not result.is_error
    body, headers = requests[0]
    if selection is None:
        assert "reader_source_connections" not in body
    else:
        assert body["reader_source_connections"] == selection
    assert headers["authorization"] == "Bearer reader-token"
    assert "cookie" not in headers
    assert len(requests) == 1


async def test_reader_browse_uses_cursor_contract_without_inventing_totals():
    requests = []

    async def canonical(request):
        requests.append((request.method, await request.json()))
        return JSONResponse(
            {"items": [], "actors": {}, "next_cursor": "c" * 43, "total": None, "total_is_exact": False}
        )

    server = create_mcp_server(
        Starlette(routes=[Route("/api/v1/tenants/north/catalog/browse", canonical, methods=["POST"])]),
        settings(),
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer reader-token"}) as session,
    ):
        result = await session.call_tool(
            "koinon_browse",
            {"tenant_id": "north", "cursor": "a" * 43, "reader_source_connections": [], "page_size": 2},
        )
    assert not result.is_error
    assert result.structured_content["total"] is None
    assert result.structured_content["total_is_exact"] is False
    assert result.structured_content["next_cursor"] == "c" * 43
    assert requests[0][0] == "POST"
    assert requests[0][1]["cursor"] == "a" * 43
    assert requests[0][1]["reader_source_connections"] == []
    assert "page" not in requests[0][1]


@pytest.mark.parametrize(
    "selection",
    [
        [
            {"provider": "google_drive", "connection_id": "one"},
            {"provider": "google_drive", "connection_id": "two"},
        ],
        [{"provider": "unknown", "connection_id": "one"}],
        [{"provider": "google_drive", "connection_id": "one", "owner_subject": "another-user"}],
        [{"provider": "google_drive", "connection_id": "one", "access_token": "not-a-credential-field"}],
    ],
)
async def test_invalid_reader_selection_never_reaches_canonical_search(selection):
    requests = []

    async def canonical(request):
        requests.append(request)
        return JSONResponse({"hits": []})

    server = create_mcp_server(
        Starlette(routes=[Route("/{path:path}", canonical, methods=["POST"])]), settings()
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer reader-token"}) as session,
    ):
        result = await session.call_tool(
            "koinon_search",
            {"tenant_id": "north", "question": "Allowed knowledge", "reader_source_connections": selection},
        )
    assert result.is_error
    assert requests == []


async def test_native_query_capture_receives_explicit_empty_reader_choices():
    requests = []

    async def capture(raw, tenant, operation, arguments):
        requests.append((raw, tenant, operation, arguments))
        return {"status": "OK", "rows": []}

    server = create_mcp_server(Starlette(), settings(), read_capture=capture)
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer reader-token"}) as session,
    ):
        result = await session.call_tool(
            "koinon_query",
            {
                "tenant_id": "north",
                "dataset_id": "data",
                "question": "Total",
                "reader_source_connections": [],
            },
        )
    assert not result.is_error
    assert requests[0][0:3] == ("reader-token", "north", "query")
    assert requests[0][3]["reader_source_connections"] == []
    assert len(requests) == 1


@pytest.mark.parametrize(
    "name,arguments",
    [
        ("koinon_fetch", {"source_id": "document", "kind": "document"}),
        ("koinon_fetch", {"source_id": "item", "kind": "catalog"}),
        ("koinon_dataset_schema", {"dataset_id": "data"}),
    ],
)
async def test_get_only_reader_choices_require_authenticated_capture(name, arguments):
    requests = []

    async def canonical(request):
        requests.append(request)
        return JSONResponse({"content": "must not be returned"})

    server = create_mcp_server(Starlette(routes=[Route("/{path:path}", canonical)]), settings())
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer reader-token"}) as session,
    ):
        result = await session.call_tool(
            name, {"tenant_id": "north", **arguments, "reader_source_connections": []}
        )
    assert result.is_error
    assert "must not be returned" not in str(result.content)
    assert requests == []
