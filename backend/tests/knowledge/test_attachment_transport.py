# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import PayloadTooLargeException
from starlette.requests import Request

from koinon.knowledge.attachments.controllers import ChatAttachmentsController


def request(body, content_type="multipart/form-data; boundary=private"):
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.disconnect"}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/",
            "headers": [(b"content-type", content_type.encode()), (b"idempotency-key", b"attempt")],
            "state": {"identity": SimpleNamespace(subject="owner")},
        },
        receive,
    )


async def test_file_upload_checks_owner_before_consuming_request(monkeypatch):
    from koinon.catalog.errors import AccessDenied

    authority = SimpleNamespace(thread=AsyncMock(side_effect=AccessDenied("Denied")))
    lifecycle = SimpleNamespace(
        reader=SimpleNamespace(authority=authority, settings=SimpleNamespace(max_file_bytes=20)),
        upload=AsyncMock(),
    )
    controller = ChatAttachmentsController(lifecycle, SimpleNamespace(), SimpleNamespace())
    monkeypatch.setattr(
        "koinon.knowledge.attachments.controllers.identity_from_request",
        lambda value: SimpleNamespace(subject="owner"),
    )
    with pytest.raises(AccessDenied):
        await controller.upload("tenant", "thread", request(b"invalid"))
    lifecycle.upload.assert_not_called()


async def test_streamed_multipart_is_bounded_before_parser_buffers_file(monkeypatch):
    lifecycle = SimpleNamespace(
        reader=SimpleNamespace(
            authority=SimpleNamespace(thread=AsyncMock()), settings=SimpleNamespace(max_file_bytes=8)
        ),
        upload=AsyncMock(),
    )
    controller = ChatAttachmentsController(lifecycle, SimpleNamespace(), SimpleNamespace())
    monkeypatch.setattr(
        "koinon.knowledge.attachments.controllers.identity_from_request",
        lambda value: SimpleNamespace(subject="owner"),
    )
    with pytest.raises(PayloadTooLargeException):
        await controller.upload("tenant", "thread", request(b"x" * 70000))
    lifecycle.upload.assert_not_called()
