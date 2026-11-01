# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import ClientDisconnect

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.document_history.download_response import original_file_response


def resource(tmp_path):
    path = tmp_path / "original"
    path.write_bytes(b"x" * (65536 + 3))
    closed = []

    async def close():
        path.unlink(missing_ok=True)
        closed.append(True)

    return SimpleNamespace(
        path=path,
        receipt=SimpleNamespace(
            bytes=65539, sha256=sha256(path.read_bytes()).hexdigest(), filename="safe\r\n.html"
        ),
        guard=AsyncMock(),
        close=close,
    ), closed


async def invoke(response, send):
    async def receive():
        await asyncio.Event().wait()

    await response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send)


async def test_original_stream_has_bounded_frames_fresh_guards_safe_headers_and_final_cleanup(tmp_path):
    owned, closed = resource(tmp_path)
    messages = []

    async def send(message):
        messages.append(message)

    await invoke(await original_file_response(owned), send)
    assert [len(message["body"]) for message in messages if message["type"] == "http.response.body"] == [
        65536,
        3,
        0,
    ]
    assert owned.guard.await_count >= 4 and closed == [True] and not owned.path.exists()
    headers = dict(messages[0]["headers"])
    assert headers[b"content-type"] == b"application/octet-stream"
    assert headers[b"content-length"] == b"65539" and b"%0D%0A" in headers[b"content-disposition"]


async def test_revocation_before_headers_releases_no_body_and_closes_the_owned_spool(tmp_path):
    owned, closed = resource(tmp_path)
    owned.guard.side_effect = AccessDenied("revoked")
    messages = []

    async def send(message):
        messages.append(message)

    with pytest.raises(AccessDenied):
        await invoke(await original_file_response(owned), send)
    assert not messages and closed == [True]


async def test_disconnect_and_midstream_revocation_never_send_a_successful_final_cut(tmp_path):
    owned, closed = resource(tmp_path)
    messages = []

    async def send(message):
        messages.append(message)
        if message["type"] == "http.response.body":
            owned.guard.side_effect = AccessDenied("revoked")

    with pytest.raises(AccessDenied):
        await invoke(await original_file_response(owned), send)
    assert closed == [True] and not any(message.get("more_body") is False for message in messages)
    owned, closed = resource(tmp_path)

    async def disconnected(message):
        if message["type"] == "http.response.body":
            raise OSError("closed")

    with pytest.raises(ClientDisconnect):
        await invoke(await original_file_response(owned), disconnected)
    assert closed == [True] and not owned.path.exists()


async def test_slow_consumer_deadline_closes_spool_without_successful_final_cut(tmp_path):
    owned, closed = resource(tmp_path)
    response = await original_file_response(owned)
    response.deadline_seconds = 0.01

    async def stalled(message):
        await asyncio.Event().wait()

    with pytest.raises(TimeoutError):
        await invoke(response, stalled)
    assert closed == [True] and not owned.path.exists()
