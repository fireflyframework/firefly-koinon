# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0

import pytest

from koinon.integrations.content_sources.read_requests import PrivateReaderResponses


@pytest.mark.asyncio
@pytest.mark.parametrize("declared", [True, False, "long"])
async def test_recorded_body_limit_precedes_dispatch_and_has_private_errors(declared):
    dispatched = False
    sent = []
    chunks = iter(
        [
            {"type": "http.request", "body": b"x" * 65536, "more_body": True},
            {"type": "http.request", "body": b"x" * 65537, "more_body": False},
        ]
    )

    async def app(scope, receive, send):
        nonlocal dispatched
        dispatched = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def receive():
        return next(chunks)

    async def send(value):
        sent.append(value)

    await PrivateReaderResponses(app)(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/tenants/tenant/evidence/recorded-document/read",
            "headers": [(b"content-length", b"9" * 5000 if declared == "long" else b"131073")]
            if declared
            else [],
        },
        receive,
        send,
    )
    assert not dispatched, "Oversized recorded request reached parsing/dispatch"
    assert sent[0]["status"] == 413
    assert dict(sent[0]["headers"])[b"cache-control"] == b"private, no-store"


@pytest.mark.asyncio
async def test_recorded_body_at_limit_is_replayed_once_to_parser():
    sent, observed = [], []
    original = {"type": "http.request", "body": b"x" * 131072, "more_body": False}

    async def app(scope, receive, send):
        observed.append(await receive())
        await send({"type": "http.response.start", "status": 422, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def receive():
        return original

    async def send(value):
        sent.append(value)

    await PrivateReaderResponses(app)(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/tenants/t/evidence/recorded-document/read",
            "headers": [],
        },
        receive,
        send,
    )
    assert observed == [original]
    assert dict(sent[0]["headers"])[b"cache-control"] == b"private, no-store"
