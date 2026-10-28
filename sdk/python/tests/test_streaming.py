# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from contextlib import asynccontextmanager

import pytest

from koinon_sdk import ApiError, KoinonClient


@asynccontextmanager
async def http_server(reply):
    tasks = set()

    async def handle(reader, writer):
        tasks.add(asyncio.current_task())
        try:
            request = await reader.readuntil(b"\r\n\r\n")
            await reply(request.decode(), reader, writer)
        finally:
            writer.close()
            await writer.wait_closed()
            tasks.discard(asyncio.current_task())

    server = await asyncio.start_server(handle, "127.0.0.1", 0)
    try:
        yield "http://127.0.0.1:" + str(server.sockets[0].getsockname()[1]) + "/api/v1"
    finally:
        server.close()
        await server.wait_closed()
        for task in tasks.copy():
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_real_http_fragmented_utf8_multiline_resume_and_fresh_token():
    seen = []

    async def reply(request, reader, writer):
        seen.append(request)
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream; charset=utf-8\r\nConnection: close\r\n\r\n"
        )
        frame = (
            '\ufeffid: 12\r\n: heartbeat\r\nevent: message_reset\r\ndata: {"text":\r\n'
            'data: "café", "status":"queued"}\r\n\r\nevent: completed\r'
            'data: {"status":"completed"}\r\r'
        ).encode()
        for byte in frame:
            writer.write(bytes([byte]))
            await writer.drain()
            await asyncio.sleep(0)

    tokens = iter(["first", "renewed"])
    async with http_server(reply) as base, KoinonClient(base, token_provider=lambda: next(tokens)) as client:
        for _ in range(2):
            async with client.events("north/division", "r/1", last_event_id="11") as events:
                rows = [event async for event in events]
                assert [(row.id, row.type) for row in rows] == [
                    ("12", "message_reset"),
                    ("12", "completed"),
                ]
                assert rows[0].data.text == "café"
    assert len(seen) == 2
    assert "GET /api/v1/tenants/north%2Fdivision/chat/runs/r%2F1/events " in seen[0]
    assert "Last-Event-ID: 11" in seen[0]
    assert "Authorization: Bearer first" in seen[0]
    assert "Authorization: Bearer renewed" in seen[1]


async def test_real_http_early_close_releases_connection():
    disconnected = asyncio.Event()

    async def reply(request, reader, writer):
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n"
            b'id: 1\ndata: {"text":"started"}\n\n'
        )
        await writer.drain()
        await reader.read()
        disconnected.set()

    async with http_server(reply) as base, KoinonClient(base, token_provider=lambda: "fresh") as client:
        async with client.events("north", "r1") as events:
            assert (await anext(events)).id == "1"
        await asyncio.wait_for(disconnected.wait(), 2)


@pytest.mark.parametrize(
    "status,content_type,body,error",
    [
        (
            403,
            "application/problem+json",
            b'{"code":"ACCESS_DENIED","detail":"Membership changed"}',
            ApiError,
        ),
        (200, "application/json", b"{}", ValueError),
        (200, "text/event-stream", b"data: " + b"x" * 1_048_577, ValueError),
    ],
)
async def test_real_http_failures_close_without_reconnect(status, content_type, body, error):
    requests = []

    async def reply(request, reader, writer):
        requests.append(request)
        writer.write(
            (
                f"HTTP/1.1 {status} Response\r\nContent-Type: {content_type}\r\nConnection: close\r\n\r\n"
            ).encode()
            + body
        )
        await writer.drain()

    async with http_server(reply) as base, KoinonClient(base, token_provider=lambda: "fresh") as client:
        with pytest.raises(error):
            async with client.events("north", "r1") as events:
                await anext(events)
    assert len(requests) == 1


async def test_real_http_cancellation_releases_connection():
    opened, disconnected = asyncio.Event(), asyncio.Event()

    async def reply(request, reader, writer):
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n")
        await writer.drain()
        opened.set()
        await reader.read()
        disconnected.set()

    async with http_server(reply) as base, KoinonClient(base, token_provider=lambda: "fresh") as client:

        async def consume():
            async with client.events("north", "r1") as events:
                return await anext(events)

        task = asyncio.create_task(consume())
        await asyncio.wait_for(opened.wait(), 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.wait_for(disconnected.wait(), 2)


async def test_sse_empty_event_persistent_id_nul_and_incomplete_eof():
    async def reply(request, reader, writer):
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n")
        frame = (
            '\ufeffid: 7\r\nevent:\r\ndata: {"text":\r\ndata: "café"}\r\n\r\n'
            'id: bad\x00id\ndata: {}\n\ndata: {"text":"unfinished"}'
        ).encode()
        for byte in frame:
            writer.write(bytes([byte]))
            await writer.drain()
            await asyncio.sleep(0)

    async with (
        http_server(reply) as base,
        KoinonClient(base, token_provider=lambda: "fresh") as client,
        client.events("t", "r") as events,
    ):
        rows = [row async for row in events]
    assert [(row.id, row.type) for row in rows] == [("7", "message"), ("7", "message")]
    assert rows[0].data.text == "café"


@pytest.mark.parametrize("frame", [b"data:\n\n", ('data: {"text":"' + "é" * 524288 + '"}\n\n').encode()])
async def test_empty_json_and_utf8_byte_oversize_rejected(frame):
    async def reply(request, reader, writer):
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: text/event-stream\r\nConnection: close\r\n\r\n" + frame
        )
        await writer.drain()

    async with http_server(reply) as base, KoinonClient(base, token_provider=lambda: "fresh") as client:
        with pytest.raises(ValueError):
            async with client.events("t", "r") as events:
                await anext(events)
