# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from test_mcp_server import protocol, settings

from koinon.mcp.server import create_mcp_server


async def test_prepare_file_upload_uses_authorized_setup_and_keeps_stage_and_chunks_app_only():
    async def prepare(raw, tenant, destination, mode):
        assert (raw, tenant, destination, mode) == ("owned-pat", "north", "collection", "document")
        return {
            "setup": {
                "tenant_id": tenant,
                "destination_id": destination,
                "destination_name": "Policies",
                "mode": mode,
                "max_file_bytes": 33554432,
                "chunk_bytes": 65536,
            }
        }

    server = create_mcp_server(Starlette(), settings(), prepare_file=prepare)
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer owned-pat"}, apps=True, modern=True) as session,
    ):
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
        assert tools["koinon_prepare_file_upload"].meta["ui"]["resourceUri"] == "ui://koinon/knowledge-review"
        assert tools["koinon_stage_file"].meta["ui"]["visibility"] == ["app"]
        assert tools["koinon_upload_file_chunk"].meta["ui"]["visibility"] == ["app"]
        result = await session.call_tool(
            "koinon_prepare_file_upload",
            {"tenant_id": "north", "destination_id": "collection", "mode": "document"},
        )
        assert not result.is_error
        assert result.structured_content["kind"] == "file_upload"
        assert result.meta["koinon/knowledgeReview"]["kind"] == "file_upload"
        assert result.structured_content["setup"]["destination_name"] == "Policies"


async def test_file_chunk_cannot_supply_download_url_or_exceed_bounded_base64_payload():
    seen = []

    async def canonical(request):
        seen.append(await request.json())
        return JSONResponse({"id": "file-review", "status": "uploading"})

    server = create_mcp_server(
        Starlette(
            routes=[
                Route(
                    "/api/v1/tenants/north/external-file-reviews/file-review/chunks",
                    canonical,
                    methods=["POST"],
                )
            ]
        ),
        settings(),
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer owned-pat"}, apps=True, modern=True) as session,
    ):
        assert "koinon_upload_file_chunk" in {tool.name for tool in (await session.list_tools()).tools}
        base = {"index": 0, "data_base64": "YWJj", "sha256": "a" * 64}
        for chunk in (
            {**base, "download_url": "https://arbitrary.example/private"},
            {**base, "data_base64": "x" * 87385},
        ):
            result = await session.call_tool(
                "koinon_upload_file_chunk", {"tenant_id": "north", "review_id": "file-review", "chunk": chunk}
            )
            assert result.is_error
    assert seen == []
