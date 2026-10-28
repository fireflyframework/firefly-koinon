# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Transport boundary independent of browser session authentication."""

import asyncio

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from koinon.mcp.settings import McpSettings


class McpHttpBoundary:
    def __init__(self, app, settings: McpSettings):
        self.app = app
        self.capacity = asyncio.Semaphore(settings.max_concurrency)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not (scope["path"] == "/mcp" or scope["path"].startswith("/mcp/")):
            return await self.app(scope, receive, send)

        async def private_send(message):
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": [
                        (key, value)
                        for key, value in message.get("headers", [])
                        if key.lower() not in {b"set-cookie", b"cache-control"}
                    ]
                    + [(b"cache-control", b"private, no-store"), (b"x-content-type-options", b"nosniff")],
                }
            await send(message)

        headers = Headers(scope=scope)
        if headers.get("cookie"):
            return await JSONResponse({"code": "MCP_COOKIES_FORBIDDEN"}, status_code=400)(
                scope, receive, private_send
            )
        if self.capacity.locked():
            return await JSONResponse(
                {"code": "MCP_CAPACITY_REACHED"}, status_code=429, headers={"Retry-After": "1"}
            )(scope, receive, private_send)
        async with self.capacity:
            await self.app(scope, receive, private_send)
