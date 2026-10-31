# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""User-picked file staging and nonce-gated approval inside the MCP review app."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import CallToolResult, TextContent

from koinon.knowledge.external_reviews.file_dtos import ExternalFileChunkInput, ExternalFileReviewInput
from koinon.mcp.private_reviews import ReviewScopeRequired
from koinon.mcp.review_tools import (
    APPROVAL,
    PRIVATE_KEY,
    PROPOSAL,
    RESOURCE_URI,
    SCOPES,
    Digest,
    Identifier,
    Key,
    Nonce,
    PrivateReview,
    Revision,
)

if TYPE_CHECKING:
    from koinon.mcp.server import CanonicalDispatcher

PrepareFile = Callable[[str, str, str, str], Awaitable[dict[str, Any]]]


def register_file_tools(
    server: MCPServer,
    api: "CanonicalDispatcher",
    *,
    oauth_enabled: bool,
    private_review: PrivateReview | None,
    prepare_file: PrepareFile | None,
):
    def metadata(*, app_only=True):
        result: dict[str, Any] = {
            "ui": {"resourceUri": RESOURCE_URI, "visibility": ["app"] if app_only else ["model", "app"]}
        }
        if oauth_enabled:
            result["securitySchemes"] = [{"type": "oauth2", "scopes": list(SCOPES)}]
        return result

    def token(ctx):
        scheme, _, raw = (ctx.headers or {}).get("authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not raw:
            raise ToolError("Authentication required (401)")
        return raw

    def result(value, *, private=None):
        if isinstance(value, CallToolResult):
            return value
        return api.bounded_result(
            CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text="Review the file operation and its recorded status in the embedded app.",
                    )
                ],
                structured_content=value,
                _meta={PRIVATE_KEY: private} if private is not None else None,
            )
        )

    async def view(ctx, tenant, value):
        if isinstance(value, CallToolResult):
            return value
        private = None
        if value.get("status") in {"uploading", "preview"} and private_review is not None:
            async with asyncio.timeout(api.settings.timeout_seconds):
                private = await private_review(token(ctx), tenant, value["id"])
            if private.get("review") != value:
                raise ToolError("The file review changed; refresh it before continuing")
            private = {**private, "kind": "file"}
        return result({"kind": "file", "review": value}, private=private)

    @server.tool(annotations=PROPOSAL, meta=metadata(app_only=False), structured_output=False)
    async def koinon_prepare_file_upload(
        tenant_id: Identifier, destination_id: Identifier, mode: Literal["document", "dataset"], ctx: Context
    ) -> CallToolResult:
        """Open the in-chat file picker for an authorized destination; the user selects the actual file."""
        if prepare_file is None:
            raise ToolError("In-chat file upload is unavailable; knowledge was not changed")
        try:
            async with asyncio.timeout(api.settings.timeout_seconds):
                setup = await prepare_file(token(ctx), tenant_id, destination_id, mode)
        except ReviewScopeRequired:
            return await api.scope_denied(ctx, SCOPES)
        private = {**setup, "kind": "file_upload"}
        return result({"kind": "file_upload", "setup": setup["setup"]}, private=private)

    @server.tool(annotations=PROPOSAL, meta=metadata(), structured_output=False)
    async def koinon_stage_file(
        tenant_id: Identifier, file: ExternalFileReviewInput, idempotency_key: Key, ctx: Context
    ) -> CallToolResult:
        """Stage the user's exact file manifest from the review app; no repository ingestion occurs."""
        if private_review is None:
            raise ToolError("In-chat file review is unavailable; knowledge was not changed")
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-file-reviews",
            body=file.model_dump(mode="json", exclude_unset=True),
            required_scopes=SCOPES,
            expected_status=(201,),
            idempotency_key=idempotency_key,
        )
        return await view(ctx, tenant_id, value)

    @server.tool(annotations=PROPOSAL, meta=metadata(), structured_output=False)
    async def koinon_file_review_status(
        tenant_id: Identifier, review_id: Identifier, ctx: Context
    ) -> CallToolResult:
        """Refresh this app's file state and private challenge without replaying ingestion."""
        value = await api.call(
            ctx,
            "GET",
            f"/api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}",
            required_scopes=SCOPES,
        )
        return await view(ctx, tenant_id, value)

    @server.tool(annotations=PROPOSAL, meta=metadata(), structured_output=False)
    async def koinon_upload_file_chunk(
        tenant_id: Identifier, review_id: Identifier, chunk: ExternalFileChunkInput, ctx: Context
    ) -> CallToolResult:
        """Store one bounded verified chunk of the user-selected file in private staging."""
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/chunks",
            body=chunk.model_dump(mode="json"),
            required_scopes=SCOPES,
        )
        return result(value if isinstance(value, CallToolResult) else {"kind": "file", "review": value})

    @server.tool(annotations=PROPOSAL, meta=metadata(), structured_output=False)
    async def koinon_seal_file(tenant_id: Identifier, review_id: Identifier, ctx: Context) -> CallToolResult:
        """Verify the complete staged file's bytes and digest before presenting its exact approval review."""
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/seal",
            required_scopes=SCOPES,
        )
        return await view(ctx, tenant_id, value)

    @server.tool(annotations=APPROVAL, meta=metadata(), structured_output=False)
    async def koinon_approve_file(
        tenant_id: Identifier,
        review_id: Identifier,
        expected_revision: Revision,
        authorization_digest: Digest,
        nonce: Nonce,
        idempotency_key: Key,
        ctx: Context,
    ) -> CallToolResult:
        """Ingest the exact file accepted in this app; never replay an unknown outcome."""
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/approve",
            body={
                "expected_revision": expected_revision,
                "authorization_digest": authorization_digest,
                "nonce": nonce,
            },
            required_scopes=SCOPES,
            expected_status=(200, 202),
            idempotency_key=idempotency_key,
        )
        return result(value if isinstance(value, CallToolResult) else {"kind": "file", "review": value})

    @server.tool(annotations=PROPOSAL, meta=metadata(), structured_output=False)
    async def koinon_cancel_file(
        tenant_id: Identifier,
        review_id: Identifier,
        expected_revision: Revision,
        authorization_digest: Digest,
        nonce: Nonce,
        ctx: Context,
    ) -> CallToolResult:
        """Cancel the exact staged file review without ingesting it into the knowledge repository."""
        value = await api.call(
            ctx,
            "POST",
            f"/api/v1/tenants/{tenant_id}/external-file-reviews/{review_id}/cancel",
            body={
                "expected_revision": expected_revision,
                "authorization_digest": authorization_digest,
                "nonce": nonce,
            },
            required_scopes=SCOPES,
        )
        return result(value if isinstance(value, CallToolResult) else {"kind": "file", "review": value})
