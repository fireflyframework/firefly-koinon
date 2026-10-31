# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import PayloadTooLargeException
from pyfly.security.context import SecurityContext
from starlette.requests import Request

from koinon.knowledge.bulk.controllers import FileBatchController


def incoming(body=b"original"):
    calls = []

    async def receive():
        calls.append(True)
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "PUT",
            "path": "/api/v1/tenants/north/sources/batches/b/items/i/content",
            "headers": [(b"idempotency-key", b"upload-key")],
        },
        receive,
    )
    request.state.security_context = SecurityContext(
        user_id="editor", attributes={"iss": "issuer", "sub": "editor"}
    )
    return request, calls


async def test_raw_controller_reserves_before_body_read_and_receipt_carries_exact_bytes():
    request, calls = incoming()
    ticket = SimpleNamespace(size_bytes=8, sha256=sha256(b"original").hexdigest(), write=True)

    async def reserve(*args):
        assert calls == []
        return ticket

    files = SimpleNamespace(
        reserve_stream=AsyncMock(side_effect=reserve),
        finish_stream=AsyncMock(return_value={"receipt_id": "registered"}),
        abort_stream=AsyncMock(),
    )
    result = await FileBatchController(files).content("north", "b", "i", request)
    assert result == {"receipt_id": "registered"} and calls == [True]
    assert files.finish_stream.call_args.args[-3:] == (b"original", 8, ticket.sha256)


async def test_stream_oversize_aborts_only_this_request_before_persisting_bytes():
    request, calls = incoming(b"larger-than-admitted")
    ticket = SimpleNamespace(size_bytes=8, sha256=sha256(b"original").hexdigest(), write=True)
    files = SimpleNamespace(
        reserve_stream=AsyncMock(return_value=ticket), finish_stream=AsyncMock(), abort_stream=AsyncMock()
    )
    with pytest.raises(PayloadTooLargeException):
        await FileBatchController(files).content("north", "b", "i", request)
    files.finish_stream.assert_not_awaited()
    files.abort_stream.assert_awaited_once_with("north", ticket)


async def test_authorization_or_permit_failure_never_reads_body():
    request, calls = incoming()
    files = SimpleNamespace(reserve_stream=AsyncMock(side_effect=PermissionError("denied")))
    with pytest.raises(PermissionError):
        await FileBatchController(files).content("north", "b", "i", request)
    assert calls == []
