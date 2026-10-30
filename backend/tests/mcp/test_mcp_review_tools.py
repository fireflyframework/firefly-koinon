# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json

from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from test_mcp_server import protocol, settings

from koinon.mcp.server import create_mcp_server

NONCE = "x" * 43
REVIEW = {
    "id": "owned-review",
    "status": "preview",
    "review": {"tenant_id": "north", "revision": 1, "authorization_digest": "a" * 64},
    "expires_at": "2026-10-30T00:00:00Z",
}
PROPOSAL = {
    "action": "create_draft",
    "destination_id": "owned-collection",
    "content": {"title": "Proposed policy", "body": "External proposed text."},
}


async def test_stage_tool_keeps_private_nonce_out_of_model_content_and_declares_in_chat_review():
    seen = []

    async def canonical(request):
        seen.append(
            (request.method, request.url.path, request.headers.get("idempotency-key"), await request.json())
        )
        return JSONResponse(REVIEW, status_code=201)

    async def private(raw, tenant, review):
        assert (raw, tenant, review) == ("owned-pat", "north", "owned-review")
        return {"review": REVIEW, "nonce": NONCE}

    app = Starlette(
        routes=[Route("/api/v1/tenants/north/external-knowledge-reviews", canonical, methods=["POST"])]
    )
    server = create_mcp_server(app, settings(), private_review=private)
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(mcp_app, {"Authorization": "Bearer owned-pat"}, apps=True, modern=True) as session,
    ):
        tools = {tool.name: tool for tool in (await session.list_tools()).tools}
        assert tools["koinon_stage_knowledge"].meta["ui"]["resourceUri"] == "ui://koinon/knowledge-review"
        assert tools["koinon_approve_knowledge"].meta["ui"]["visibility"] == ["app"]
        result = await session.call_tool(
            "koinon_stage_knowledge",
            {"tenant_id": "north", "proposal": PROPOSAL, "idempotency_key": "owned-stage-key"},
        )
        assert not result.is_error
        assert result.structured_content == {"review": REVIEW}
        assert NONCE not in json.dumps(result.structured_content) and NONCE not in str(result.content)
        assert result.meta["koinon/knowledgeReview"]["nonce"] == NONCE
    assert seen == [("POST", "/api/v1/tenants/north/external-knowledge-reviews", "owned-stage-key", PROPOSAL)]


async def test_approval_is_app_only_and_sends_exact_decision_and_key_to_fixed_native_route():
    seen = []

    async def canonical(request):
        seen.append((request.url.path, request.headers.get("idempotency-key"), await request.json()))
        return JSONResponse(
            {
                "status": "pending",
                "operation_id": "owned-operation",
                "intent_id": "owned-review",
                "reason": "commit_outcome_unresolved",
            },
            status_code=202,
        )

    app = Starlette(
        routes=[
            Route(
                "/api/v1/tenants/north/external-knowledge-reviews/owned-review/approve",
                canonical,
                methods=["POST"],
            )
        ]
    )
    server = create_mcp_server(app, settings())
    decision = {"expected_revision": 1, "authorization_digest": "a" * 64, "nonce": NONCE}
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(mcp_app, {"Authorization": "Bearer owned-pat"}, apps=True, modern=True) as session,
    ):
        result = await session.call_tool(
            "koinon_approve_knowledge",
            {
                "tenant_id": "north",
                "review_id": "owned-review",
                **decision,
                "idempotency_key": "owned-approval-key",
            },
        )
        assert not result.is_error and result.structured_content["status"] == "pending"
        assert NONCE not in json.dumps(result.structured_content) and NONCE not in str(result.content)
    assert seen == [
        (
            "/api/v1/tenants/north/external-knowledge-reviews/owned-review/approve",
            "owned-approval-key",
            decision,
        )
    ]


async def test_external_proposal_cannot_claim_user_statement_origin_or_unbounded_body():
    server = create_mcp_server(Starlette(), settings())
    mcp_app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=settings().transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(mcp_app, {"Authorization": "Bearer owned-pat"}, apps=True, modern=True) as session,
    ):
        assert "koinon_stage_knowledge" in {tool.name for tool in (await session.list_tools()).tools}
        for proposal in (
            {**PROPOSAL, "origin": {"kind": "user_statement"}},
            {**PROPOSAL, "content": {"title": "Oversized", "body": "x" * 262145}},
        ):
            result = await session.call_tool(
                "koinon_stage_knowledge",
                {"tenant_id": "north", "proposal": proposal, "idempotency_key": "owned-stage-key"},
            )
            assert result.is_error


async def test_private_app_payload_counts_toward_response_limit():
    async def canonical(request):
        return JSONResponse(REVIEW, status_code=201)

    async def private(*args):
        return {"review": REVIEW, "nonce": NONCE, "presentation": {"product_name": "x" * 2048}}

    configuration = settings()
    configuration.max_response_bytes = 1024
    server = create_mcp_server(
        Starlette(
            routes=[Route("/api/v1/tenants/north/external-knowledge-reviews", canonical, methods=["POST"])]
        ),
        configuration,
        private_review=private,
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=configuration.transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer owned-pat"}, apps=True, modern=True) as session,
    ):
        result = await session.call_tool(
            "koinon_stage_knowledge", {"tenant_id": "north", "proposal": PROPOSAL, "idempotency_key": "stage"}
        )
    assert result.is_error and NONCE not in str(result.content)
    assert "koinon/knowledgeReview" not in (result.meta or {})
    assert NONCE not in json.dumps(result.meta)


async def test_private_review_callback_has_the_configured_timeout():
    import asyncio

    async def canonical(request):
        return JSONResponse(REVIEW, status_code=201)

    async def private(*args):
        await asyncio.sleep(2)
        return {"review": REVIEW, "nonce": NONCE}

    configuration = settings()
    configuration.timeout_seconds = 1
    server = create_mcp_server(
        Starlette(
            routes=[Route("/api/v1/tenants/north/external-knowledge-reviews", canonical, methods=["POST"])]
        ),
        configuration,
        private_review=private,
    )
    app = server.streamable_http_app(
        stateless_http=True, json_response=True, transport_security=configuration.transport_security()
    )
    async with (
        server.session_manager.run(),
        protocol(app, {"Authorization": "Bearer owned-pat"}, apps=True, modern=True) as session,
    ):
        result = await session.call_tool(
            "koinon_stage_knowledge", {"tenant_id": "north", "proposal": PROPOSAL, "idempotency_key": "stage"}
        )
    assert result.is_error and "timed out" in str(result.content).lower()
    assert NONCE not in str(result.content)
