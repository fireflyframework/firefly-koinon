# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from koinon.mcp.server import create_mcp_server
from koinon.mcp.settings import McpSettings


@asynccontextmanager
async def protocol(app, headers=None):
    async with (
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app), headers=headers or {}, base_url="http://testserver"
        ) as http,
        streamable_http_client("http://testserver/mcp", http_client=http) as streams,
        ClientSession(streams[0], streams[1]) as session,
    ):
        await session.initialize()
        yield session


def settings():
    return McpSettings(enabled=True, public_url="http://127.0.0.1:18781/mcp", allowed_hosts=["testserver"])


def test_disabled_default_and_untrusted_deployment_configuration():
    assert McpSettings().enabled is False
    with pytest.raises(ValueError, match="public_url"):
        McpSettings(enabled=True)
    with pytest.raises(ValueError):
        McpSettings(enabled=True, public_url="http://remote.example/mcp")
    with pytest.raises(ValueError):
        McpSettings(enabled=True, public_url="https://koinon.example/other")


async def test_real_protocol_uses_canonical_route_and_isolates_context_and_credentials():
    seen = []

    async def canonical(request: Request):
        seen.append((request.url.path, dict(request.headers), SecurityContextHolder.get_context()))
        return JSONResponse({"tenants": [{"id": "north"}], "source_version_id": "original-version"})

    canonical_app = Starlette(routes=[Route("/api/v1/context", canonical)])
    server = create_mcp_server(canonical_app, settings())
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with server.session_manager.run():
        with SecurityContextHolder.using(SecurityContext(user_id="outer")):
            async with protocol(
                mcp_app, {"Authorization": "Bearer same-service", "Cookie": "secret=browser"}
            ) as session:
                names = {tool.name for tool in (await session.list_tools()).tools}
                assert {
                    "koinon_context",
                    "koinon_list",
                    "koinon_search",
                    "koinon_fetch",
                    "koinon_dataset_schema",
                    "koinon_query",
                    "koinon_answer_audit",
                    "koinon_provenance",
                } <= names
                assert not any("confirm" in name or "write" in name for name in names)
                result = await session.call_tool("koinon_context", {})
                assert not result.is_error
                assert result.structured_content["source_version_id"] == "original-version"
            assert SecurityContextHolder.get_context().user_id == "outer"
    path, headers, identity = seen[0]
    assert path == "/api/v1/context"
    assert headers["authorization"] == "Bearer same-service"
    assert "cookie" not in headers
    assert headers["host"] == "koinon.internal"
    assert identity is None


async def test_protocol_rejects_path_injection_and_bounded_inputs_before_dispatch():
    seen = []

    async def canonical(request):
        seen.append(request.url.path)
        return JSONResponse({})

    canonical_app = Starlette(routes=[Route("/{path:path}", canonical)])
    server = create_mcp_server(canonical_app, settings())
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(mcp_app, {"Authorization": "Bearer same-service"}) as session,
    ):
        for arguments in ({"tenant_id": "../south"}, {"tenant_id": "north", "page_size": 101}):
            result = await session.call_tool("koinon_list", arguments)
            assert result.is_error
        result = await session.call_tool("koinon_search", {"tenant_id": "north", "question": "x" * 8001})
        assert result.is_error
    assert seen == []


async def test_canonical_denial_is_tool_error_without_disclosing_response_or_token():
    async def canonical(request):
        return JSONResponse(
            {"code": "TOKEN_SCOPE_DENIED", "detail": "secret internal detail"}, status_code=403
        )

    server = create_mcp_server(Starlette(routes=[Route("/api/v1/context", canonical)]), settings())
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(mcp_app, {"Authorization": "Bearer secret-token"}) as session,
    ):
        result = await session.call_tool("koinon_context", {})
        assert result.is_error
        text = str(result.content)
        assert "403" in text
        assert "TOKEN_SCOPE_DENIED" in text
        assert "secret" not in text


async def test_response_size_limit_stops_canonical_output_before_exposing_partial_content():
    async def canonical(request):
        return JSONResponse({"content": "private" * 1000})

    limits = settings()
    limits.max_response_bytes = 1024
    server = create_mcp_server(Starlette(routes=[Route("/api/v1/context", canonical)]), limits)
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=limits.transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(mcp_app, {"Authorization": "Bearer same-service"}) as session,
    ):
        result = await session.call_tool("koinon_context", {})
        assert result.is_error
        assert "response limit" in str(result.content)
        assert "private" not in str(result.content)


async def test_credential_mapping_revocation_is_an_authenticated_error_without_internal_details():
    from pyfly.kernel import UnauthorizedException

    async def revoked(raw):
        raise UnauthorizedException("Internal revoked credential detail", code="INVALID_TOKEN")

    limits = settings()
    server = create_mcp_server(Starlette(), limits, revoked)
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=limits.transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(mcp_app, {"Authorization": "Bearer previous-token"}) as session,
    ):
        result = await session.call_tool("koinon_context", {})
        assert result.is_error
        assert "401" in str(result.content)
        assert "Internal" not in str(result.content)
