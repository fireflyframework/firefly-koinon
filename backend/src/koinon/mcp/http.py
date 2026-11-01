# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Transport boundary independent of browser session authentication."""

import asyncio
from time import monotonic

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from koinon.mcp.observations import MetricsResolver, Outcome, RecorderResolver, observe
from koinon.mcp.settings import McpSettings


class McpHttpBoundary:
    def __init__(
        self,
        app,
        settings: McpSettings,
        *,
        activity_recorder: RecorderResolver | None = None,
        activity_metrics: MetricsResolver | None = None,
    ):
        self.app = app
        self.capacity = asyncio.Semaphore(settings.max_concurrency)
        self.activity_recorder, self.activity_metrics = activity_recorder, activity_metrics

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not (scope["path"] == "/mcp" or scope["path"].startswith("/mcp/")):
            return await self.app(scope, receive, send)

        started = monotonic()
        outcome: Outcome = "failed"

        async def private_send(message):
            nonlocal outcome
            if message["type"] == "http.response.start":
                status = message["status"]
                outcome = "rejected" if 400 <= status < 500 else "failed" if status >= 500 else "succeeded"
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

        try:
            await self._dispatch(scope, receive, private_send)
        except asyncio.CancelledError:
            outcome = "cancelled"
            raise
        except Exception:
            outcome = "failed"
            raise
        finally:
            if scope.get("method") in {"GET", "POST", "DELETE"}:
                await observe(
                    scope,
                    "request",
                    scope["method"],
                    outcome,
                    started,
                    self.activity_recorder,
                    self.activity_metrics,
                )

    async def _dispatch(self, scope, receive, private_send):
        headers = Headers(scope=scope)
        if headers.get("cookie"):
            return await JSONResponse({"code": "MCP_COOKIES_FORBIDDEN"}, status_code=400)(
                scope, receive, private_send
            )
        if scope.get("method") == "GET":
            # Legacy SSE channels have SDK session admission bounds; keeping an operation
            # permit for their lifetime would prevent their own subsequent tool calls.
            return await self.app(scope, receive, private_send)
        if self.capacity.locked():
            return await JSONResponse(
                {"code": "MCP_CAPACITY_REACHED"}, status_code=429, headers={"Retry-After": "1"}
            )(scope, receive, private_send)
        async with self.capacity:
            await self.app(scope, receive, private_send)
