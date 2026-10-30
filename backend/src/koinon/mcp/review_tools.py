# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Expose proposals to models and private approval challenges only to the in-chat app."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated, Any

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import Field

from koinon.knowledge.external_reviews.dtos import ExternalReviewInput

if TYPE_CHECKING:
    from koinon.mcp.server import CanonicalDispatcher

RESOURCE_URI = "ui://koinon/knowledge-review"
RESOURCE_MIME = "text/html;profile=mcp-app"
PRIVATE_KEY = "koinon/knowledgeReview"
SCOPES = ("catalog:read", "catalog:write", "ingest:write")
Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]
Key = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")]
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Nonce = Annotated[str, Field(min_length=43, max_length=43, pattern=r"^[A-Za-z0-9_-]+$")]
Revision = Annotated[int, Field(ge=1)]
PrivateReview = Callable[[str, str, str], Awaitable[dict[str, Any]]]
PROPOSAL = ToolAnnotations(
    read_only_hint=False, destructive_hint=False, idempotent_hint=True, open_world_hint=False
)
APPROVAL = ToolAnnotations(
    read_only_hint=False, destructive_hint=True, idempotent_hint=True, open_world_hint=False
)


def register_review_tools(
    server: MCPServer,
    api: "CanonicalDispatcher",
    *,
    oauth_enabled: bool,
    private_review: PrivateReview | None,
):
    def metadata(*, app_only=False):
        result: dict[str, Any] = {
            "ui": {"resourceUri": RESOURCE_URI, "visibility": ["app"] if app_only else ["model", "app"]}
        }
        if oauth_enabled:
            result["securitySchemes"] = [{"type": "oauth2", "scopes": list(SCOPES)}]
        return result

    def public_result(value):
        if isinstance(value, CallToolResult):
            return value
        return api.bounded_result(
            CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="Knowledge operation result. Inspect its recorded status and receipt.",
                    )
                ],
                structured_content=value,
            )
        )

    async def presentation(ctx, tenant, value):
        if isinstance(value, CallToolResult):
            return value
        public = {"review": value}
        secret = None
        if value.get("status") == "preview" and private_review is not None:
            header = (ctx.headers or {}).get("authorization", "")
            scheme, _, raw = header.partition(" ")
            if scheme.lower() != "bearer" or not raw:
                raise ToolError("Authentication required (401)")
            try:
                async with asyncio.timeout(api.settings.timeout_seconds):
                    secret = await private_review(raw, tenant, value["id"])
            except TimeoutError as error:
                raise ToolError("Private knowledge review timed out; refresh before continuing") from error
            if secret.get("review") != value:
                raise ToolError("The review changed; refresh the in-chat review")
        return api.bounded_result(
            CallToolResult(
                content=[
                    TextContent(
                        type="text", text="Review the exact proposed knowledge change in the embedded app."
                    )
                ],
                structured_content=public,
                _meta={PRIVATE_KEY: secret} if secret is not None else None,
            )
        )

    @server.tool(annotations=PROPOSAL, meta=metadata(), structured_output=False)
    async def koinon_stage_knowledge(
        tenant_id: Identifier, proposal: ExternalReviewInput, idempotency_key: Key, ctx: Context
    ) -> CallToolResult:
        """Propose exact external content for in-chat human review; never publishes or approves it."""
        if private_review is None:
            raise ToolError("In-chat knowledge review is unavailable; knowledge was not changed")
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-knowledge-reviews",
            body=proposal.model_dump(mode="json", exclude_unset=True),
            required_scopes=SCOPES,
            expected_status=(201,),
            idempotency_key=idempotency_key,
        )
        return await presentation(ctx, tenant_id, value)

    @server.tool(annotations=PROPOSAL, meta=metadata(app_only=True), structured_output=False)
    async def koinon_review_status(
        tenant_id: Identifier, review_id: Identifier, ctx: Context
    ) -> CallToolResult:
        """Refresh this app's exact review and private approval challenge; no knowledge mutation."""
        value = await api.call(
            ctx,
            "GET",
            f"/api/v1/tenants/{tenant_id}/external-knowledge-reviews/{review_id}",
            required_scopes=SCOPES,
        )
        return await presentation(ctx, tenant_id, value)

    @server.tool(annotations=APPROVAL, meta=metadata(app_only=True), structured_output=False)
    async def koinon_approve_knowledge(
        tenant_id: Identifier,
        review_id: Identifier,
        expected_revision: Revision,
        authorization_digest: Digest,
        nonce: Nonce,
        idempotency_key: Key,
        ctx: Context,
    ) -> dict[str, Any] | CallToolResult:
        """Apply only the exact review accepted by the user in this app, with its private one-use nonce."""
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-knowledge-reviews/{review_id}/approve",
            body={
                "expected_revision": expected_revision,
                "authorization_digest": authorization_digest,
                "nonce": nonce,
            },
            required_scopes=SCOPES,
            expected_status=(200, 202),
            idempotency_key=idempotency_key,
        )
        return public_result(value)

    @server.tool(annotations=PROPOSAL, meta=metadata(app_only=True), structured_output=False)
    async def koinon_cancel_knowledge(
        tenant_id: Identifier,
        review_id: Identifier,
        expected_revision: Revision,
        authorization_digest: Digest,
        nonce: Nonce,
        ctx: Context,
    ) -> dict[str, Any] | CallToolResult:
        """Cancel this exact app review without publishing any knowledge."""
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-knowledge-reviews/{review_id}/cancel",
            body={
                "expected_revision": expected_revision,
                "authorization_digest": authorization_digest,
                "nonce": nonce,
            },
            required_scopes=SCOPES,
        )
        return public_result(value)

    @server.resource(
        RESOURCE_URI,
        name="koinon knowledge review",
        mime_type=RESOURCE_MIME,
        meta={"ui": {"prefersBorder": True, "csp": {"connectDomains": [], "resourceDomains": []}}},
    )
    def review_resource() -> str:
        from koinon.mcp.review_resource import render_review_resource

        return render_review_resource()
