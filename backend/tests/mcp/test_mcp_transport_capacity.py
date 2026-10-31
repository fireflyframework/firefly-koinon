# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio

import pytest
from starlette.responses import JSONResponse

from koinon.mcp.http import McpHttpBoundary
from koinon.mcp.settings import McpSettings


@pytest.mark.parametrize("held_method,expected", [("GET", 200), ("POST", 429)])
async def test_legacy_channels_do_not_take_operation_permits_but_tool_posts_remain_bounded(
    held_method, expected
):
    started, release = asyncio.Event(), asyncio.Event()

    async def application(scope, receive, send):
        if scope["method"] == held_method:
            started.set()
            await release.wait()
        await JSONResponse({"ok": True})(scope, receive, send)

    boundary = McpHttpBoundary(application, McpSettings(max_concurrency=1))
    base = {"type": "http", "path": "/mcp", "headers": []}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    channel = []

    async def channel_send(message):
        channel.append(message)

    stream = asyncio.create_task(boundary({**base, "method": held_method}, receive, channel_send))
    await asyncio.wait_for(started.wait(), 1)
    messages = []

    async def send(message):
        messages.append(message)

    try:
        await asyncio.wait_for(boundary({**base, "method": "POST"}, receive, send), 1)
        assert messages[0]["status"] == expected
    finally:
        release.set()
        await stream
