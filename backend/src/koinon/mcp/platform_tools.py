# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Only current unbounded organization administrators discover the two operational read tools."""

import asyncio
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Annotated, Any

from mcp import types
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver import Context
from pydantic import Field
from pyfly.context import ApplicationContext

from koinon.mcp.private_reviews import authenticated_operation
from koinon.platform.authority import PlatformAccess
from koinon.tokens.authorization import TokenRestriction

if TYPE_CHECKING:
    from pyfly.mcp import McpServer

    from koinon.mcp.server import CanonicalDispatcher

Identifier = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")]

PLATFORM_TOOLS = frozenset({"koinon_platform_health", "koinon_system_information"})
PLATFORM_SCOPES = ("catalog:read", "audit:read")
PlatformAuthorization = Callable[[str], Awaitable[bool]]


def platform_authorization(context: ApplicationContext) -> PlatformAuthorization:
    async def allowed(raw: str) -> bool:
        async def work(principal):
            restriction = context.get_bean(TokenRestriction)
            grant = await restriction.grant(principal)
            if grant is None:
                return {"allowed": False}
            await context.get_bean(PlatformAccess).resolve(principal, grant.tenant_id)
            return {"allowed": True}

        try:
            result = await authenticated_operation(context, raw, work)
            return result == {"allowed": True}
        except Exception:
            return False

    return allowed


def install_platform_visibility(server: "McpServer", authorized: PlatformAuthorization | None) -> None:
    async def permitted(ctx: ServerRequestContext) -> bool:
        if authorized is None or ctx.request is None:
            return False
        header = ctx.request.headers.get("authorization", "")
        scheme, _, raw = header.partition(" ")
        if scheme.lower() != "bearer" or not raw or len(raw) > 8192:
            return False
        try:
            async with asyncio.timeout(2):
                return await authorized(raw)
        except Exception:
            return False

    async def boundary(ctx: ServerRequestContext, call_next: CallNext) -> HandlerResult:
        if ctx.method == "tools/list":
            result = await call_next(ctx)
            if not await permitted(ctx):
                if isinstance(result, types.ListToolsResult):
                    return result.model_copy(
                        update={"tools": [tool for tool in result.tools if tool.name not in PLATFORM_TOOLS]}
                    )
                if isinstance(result, dict) and isinstance(result.get("tools"), list):
                    return {
                        **result,
                        "tools": [tool for tool in result["tools"] if tool.get("name") not in PLATFORM_TOOLS],
                    }
            return result
        if (
            ctx.method == "tools/call"
            and ctx.params is not None
            and ctx.params.get("name") in PLATFORM_TOOLS
            and not await permitted(ctx)
        ):
            return types.CallToolResult(
                is_error=True,
                content=[
                    types.TextContent(
                        type="text",
                        text=(
                            "Current organization administrator access with an "
                            "unbounded audit token is required (403)."
                        ),
                    )
                ],
            )
        return await call_next(ctx)

    server.registry.middleware.insert(0, boundary)


def register_platform_tools(server: "McpServer", api: "CanonicalDispatcher") -> None:
    annotations = types.ToolAnnotations(
        read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False
    )

    @server.tool(annotations=annotations, structured_output=True)
    async def koinon_platform_health(tenant_id: Identifier, ctx: Context) -> dict[str, Any]:
        """Read passive platform observations with an organization-wide administrator PAT.

        Workspace-bound OAuth grants cannot use this tool. No model or delivery probe is performed.
        """
        return await api.call(
            ctx, "GET", f"/api/v1/tenants/{tenant_id}/platform/health", required_scopes=PLATFORM_SCOPES
        )

    @server.tool(annotations=annotations, structured_output=True)
    async def koinon_system_information(tenant_id: Identifier, ctx: Context) -> dict[str, Any]:
        """Read allowlisted installed component information with an organization-wide administrator PAT.

        Workspace-bound OAuth grants cannot use this tool. Build or artifact absence remains unknown.
        """
        return await api.call(
            ctx,
            "GET",
            f"/api/v1/tenants/{tenant_id}/platform/system-information",
            required_scopes=PLATFORM_SCOPES,
        )
