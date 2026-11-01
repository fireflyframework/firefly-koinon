# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.core import Config
from pyfly.kernel import PayloadTooLargeException
from pyfly.security.context import SecurityContext
from starlette.requests import Request

from koinon.knowledge.bulk.controllers import FileBatchController
from koinon.storage.scratch import ScratchAdmission


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

    async def finish(*args):
        path, size, digest = args[-3:]
        assert path.read_bytes() == b"original" and size == 8 and digest == ticket.sha256
        return {"receipt_id": "registered"}

    files = SimpleNamespace(
        reserve_stream=AsyncMock(side_effect=reserve),
        finish_stream=AsyncMock(side_effect=finish),
        abort_stream=AsyncMock(),
    )
    result = await FileBatchController(files, ScratchAdmission(Config({}))).content(
        "north", "b", "i", request
    )
    assert result == {"receipt_id": "registered"} and calls == [True]
    assert not files.finish_stream.call_args.args[-3].exists()


async def test_stream_oversize_aborts_only_this_request_before_persisting_bytes():
    request, calls = incoming(b"larger-than-admitted")
    ticket = SimpleNamespace(size_bytes=8, sha256=sha256(b"original").hexdigest(), write=True)
    files = SimpleNamespace(
        reserve_stream=AsyncMock(return_value=ticket), finish_stream=AsyncMock(), abort_stream=AsyncMock()
    )
    with pytest.raises(PayloadTooLargeException):
        await FileBatchController(files, ScratchAdmission(Config({}))).content("north", "b", "i", request)
    files.finish_stream.assert_not_awaited()
    files.abort_stream.assert_awaited_once_with("north", ticket)


async def test_authorization_or_permit_failure_never_reads_body():
    request, calls = incoming()
    files = SimpleNamespace(reserve_stream=AsyncMock(side_effect=PermissionError("denied")))
    with pytest.raises(PermissionError):
        await FileBatchController(files, ScratchAdmission(Config({}))).content("north", "b", "i", request)
    assert calls == []


async def test_shared_scratch_rejection_precedes_body_and_releases_the_owned_writer():
    request, calls = incoming()
    ticket = SimpleNamespace(size_bytes=8, sha256=sha256(b"original").hexdigest(), write=True)
    files = SimpleNamespace(
        reserve_stream=AsyncMock(return_value=ticket), finish_stream=AsyncMock(), abort_stream=AsyncMock()
    )
    scratch = ScratchAdmission(Config({"koinon": {"knowledge": {"ingestion": {"scratch_max_bytes": 8}}}}))
    with pytest.raises(PayloadTooLargeException):
        await FileBatchController(files, scratch).content("north", "b", "i", request)
    assert not calls and scratch.available_bytes == 8
    files.abort_stream.assert_awaited_once_with("north", ticket)
    files.finish_stream.assert_not_awaited()
