# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager

import httpx2
import pytest
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from test_mcp_review_tools import NONCE, PROPOSAL, REVIEW
from test_mcp_server import settings

from koinon.mcp.server import create_mcp_server

KEY = "io.modelcontextprotocol/ui"
MIME = "text/html;profile=mcp-app"


@asynccontextmanager
async def connection(app, *, apps=True, modern=False, mime=MIME):
    async with (
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app),
            base_url="http://testserver",
            headers={"Authorization": "Bearer owned-pat"},
        ) as http,
        streamable_http_client("http://testserver/mcp", http_client=http) as streams,
        ClientSession(
            streams[0], streams[1], extensions={KEY: {"mimeTypes": [mime]}} if apps else None
        ) as client,
    ):
        if modern:
            await client.discover()
        else:
            await client.initialize()
        yield client


def prepared(*, stateless=False):
    calls = []

    async def canonical(request):
        calls.append(request.url.path)
        return JSONResponse(REVIEW, status_code=201)

    async def private(*args):
        calls.append("private")
        return {"review": REVIEW, "nonce": NONCE}

    server = create_mcp_server(
        Starlette(
            routes=[Route("/api/v1/tenants/north/external-knowledge-reviews", canonical, methods=["POST"])]
        ),
        settings(),
        private_review=private,
    )
    app = server.streamable_http_app(
        stateless_http=stateless,
        json_response=True,
        max_sessions=2,
        session_idle_timeout=30,
        transport_security=settings().transport_security(),
    )
    return server, app, calls


@pytest.mark.parametrize("apps,mime", [(False, MIME), (True, "text/html")])
async def test_unnegotiated_or_wrong_mime_is_blocked_before_proposal_and_private_nonce(apps, mime):
    server, app, calls = prepared()
    async with server.session_manager.run(), connection(app, apps=apps, mime=mime) as client:
        result = await client.call_tool(
            "koinon_stage_knowledge", {"tenant_id": "north", "proposal": PROPOSAL, "idempotency_key": "stage"}
        )
        assert result.is_error and result.meta is None
        assert "MCP Apps" in str(result.content)
    assert calls == []


@pytest.mark.parametrize("stateless,modern", [(False, False), (True, True)])
async def test_negotiated_legacy_session_and_modern_envelope_both_allow_exact_review(stateless, modern):
    server, app, calls = prepared(stateless=stateless)
    async with server.session_manager.run(), connection(app, modern=modern) as client:
        if modern:
            assert KEY in client.server_capabilities.extensions
        result = await client.call_tool(
            "koinon_stage_knowledge", {"tenant_id": "north", "proposal": PROPOSAL, "idempotency_key": "stage"}
        )
        assert not result.is_error
        assert result.meta["koinon/knowledgeReview"]["nonce"] == NONCE
    assert calls == ["/api/v1/tenants/north/external-knowledge-reviews", "private"]


@pytest.mark.parametrize(
    "name",
    [
        "koinon_stage_knowledge",
        "koinon_prepare_file_upload",
        "koinon_review_status",
        "koinon_approve_knowledge",
        "koinon_cancel_knowledge",
        "koinon_stage_file",
        "koinon_file_review_status",
        "koinon_upload_file_chunk",
        "koinon_seal_file",
        "koinon_approve_file",
        "koinon_cancel_file",
    ],
)
async def test_all_management_tools_reject_missing_apps_before_any_callback(name):
    server, app, calls = prepared()
    async with server.session_manager.run(), connection(app, apps=False) as client:
        result = await client.call_tool(name, {})
        assert result.is_error and "MCP Apps" in str(result.content)
        assert "koinon/knowledgeReview" not in (result.meta or {})
    assert calls == []


async def test_legacy_idle_session_is_expired_by_the_sdk_transport():
    import asyncio

    server, _, _ = prepared()
    app = server.streamable_http_app(
        stateless_http=False,
        json_response=True,
        max_sessions=1,
        session_idle_timeout=0.05,
        transport_security=settings().transport_security(),
    )
    async with (
        server.session_manager.run(),
        httpx2.AsyncClient(transport=httpx2.ASGITransport(app), base_url="http://testserver") as http,
    ):
        opened = await http.post(
            "/mcp",
            headers={"Accept": "application/json, text/event-stream"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "owned-idle-client", "version": "1"},
                },
            },
        )
        assert opened.status_code == 200
        session = opened.headers["mcp-session-id"]
        await asyncio.sleep(0.12)
        expired = await http.post(
            "/mcp",
            headers={
                "Accept": "application/json, text/event-stream",
                "MCP-Session-Id": session,
                "MCP-Protocol-Version": "2025-11-25",
            },
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        assert expired.status_code == 404
