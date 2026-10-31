# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Require negotiated UI support before creating or disclosing a private review."""

from typing import Any

from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.extension import Extension
from mcp.types import CallToolRequestParams, CallToolResult, TextContent

APPS_EXTENSION = "io.modelcontextprotocol/ui"
REVIEW_MIME = "text/html;profile=mcp-app"


class KnowledgeReviewExtension(Extension):
    identifier = APPS_EXTENSION

    def __init__(self, tools: frozenset[str]):
        self.review_tools = tools

    def settings(self) -> dict[str, Any]:
        return {"mimeTypes": [REVIEW_MIME]}

    async def intercept_tool_call(
        self, params: CallToolRequestParams, ctx: ServerRequestContext[Any, Any], call_next: CallNext
    ) -> HandlerResult:
        if params.name in self.review_tools:
            capabilities = ctx.session.client_capabilities
            extensions = capabilities.extensions if capabilities else None
            declared = extensions.get(APPS_EXTENSION) if extensions else None
            mime_types = declared.get("mimeTypes") if isinstance(declared, dict) else None
            if not isinstance(mime_types, list) or REVIEW_MIME not in mime_types:
                return CallToolResult(
                    is_error=True,
                    content=[
                        TextContent(
                            type="text",
                            text=(
                                "This operation requires negotiated MCP Apps support. "
                                "Reconnect from a compatible "
                                "client that can show the private knowledge review. "
                                "Retrieval remains available; "
                                "repository knowledge was not changed."
                            ),
                        )
                    ],
                )
        return await call_next(ctx)
