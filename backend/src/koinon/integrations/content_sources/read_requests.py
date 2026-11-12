# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private request intent shared by typed read adapters, never a permission grant."""

import re
from contextlib import asynccontextmanager
from typing import Any

from pydantic import TypeAdapter
from pyfly.web.adapters.starlette.errors import global_exception_handler
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_context import reader_source_snapshot
from koinon.integrations.content_sources.read_errors import source_problem
from koinon.security.identity import identity_from_request

_json = TypeAdapter(Any)
PRIVATE_HEADERS = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}

_PRIVATE_READ_PATHS = tuple(
    re.compile(r"/api/v1/tenants/[^/]+/" + path)
    for path in (
        r"catalog/[^/]+/read",
        r"catalog/availability",
        r"knowledge-processing",
        r"datasets/[^/]+/schema/read",
        r"lineage/read",
        r"documents/[^/]+/chunks/read",
        r"documents/[^/]+/original/read",
        r"documents/[^/]+/versions/read",
        r"documents/[^/]+/versions/[^/]+/read",
        r"documents/[^/]+/versions/[^/]+/extractions/read",
        r"documents/[^/]+/versions/[^/]+/extractions/[^/]+/parts/read",
        r"documents/[^/]+/versions/[^/]+/extractions/[^/]+/parts/[^/]+/read",
        r"documents/[^/]+/versions/[^/]+/original/read",
        r"datasets/[^/]+/tables/[^/]+/(?:provenance|snapshots|coordinates)/read",
        r"datasets/[^/]+/tables/[^/]+/coordinates/(?:rows/read|columns/read|cells)",
        r"knowledge-items/[^/]+/read",
        r"knowledge-items/[^/]+/versions/[^/]+/read",
        r"exports/[^/]+/read",
        r"exports/[^/]+/download/read",
        r"shares/[^/]+/read",
        r"chat/threads/[^/]+/read",
        r"evidence/recorded-document/read",
    )
)


def private_reader_request(scope):
    return (
        scope["type"] == "http"
        and scope["method"] == "POST"
        and any(pattern.fullmatch(scope["path"]) for pattern in _PRIVATE_READ_PATHS)
    )


async def private_reader_problem(request: Request, error: Exception) -> Response:
    response = await global_exception_handler(request, error)
    if private_reader_request(request.scope) and response.status_code in (400, 422):
        return JSONResponse(
            {
                "type": "about:blank",
                "title": "Invalid read request",
                "status": response.status_code,
                "detail": "Check the read request fields.",
            },
            status_code=response.status_code,
            headers=PRIVATE_HEADERS,
            media_type="application/problem+json",
        )
    return response


class PrivateReaderResponses:
    """Apply privacy headers even when validation or CSRF denies before dispatch."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        protected = private_reader_request(scope)
        recorded = protected and re.fullmatch(
            r"/api/v1/tenants/[^/]+/evidence/recorded-document/read", scope["path"]
        )
        if recorded:
            maximum = 128 * 1024
            length = next(
                (value for key, value in scope.get("headers", ()) if key.lower() == b"content-length"), b""
            )
            normalized_length = length.lstrip(b"0")
            oversized = length.isdigit() and (
                len(normalized_length) > 6 or len(normalized_length) == 6 and normalized_length > b"131072"
            )
            chunks, size = [], 0
            while not oversized:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                size += len(message.get("body", b""))
                if size > maximum:
                    oversized = True
                    break
                chunks.append(message)
                if not message.get("more_body", False):
                    break
            if oversized:
                response = JSONResponse(
                    {"type": "about:blank", "title": "Read request too large", "status": 413},
                    status_code=413,
                    headers=PRIVATE_HEADERS,
                    media_type="application/problem+json",
                )
                await response(scope, receive, send)
                return
            original_receive = receive
            buffered = iter(chunks)

            async def replay():
                try:
                    return next(buffered)
                except StopIteration:
                    return await original_receive()

            receive = replay

        async def private_send(message):
            if message["type"] == "http.response.start":
                headers = [
                    (key, value)
                    for key, value in message.get("headers", ())
                    if key.lower() not in (b"cache-control", b"x-content-type-options")
                ]
                message = {
                    **message,
                    "headers": headers
                    + [(key.lower().encode(), value.encode()) for key, value in PRIVATE_HEADERS.items()],
                }
            await send(message)

        await self.app(scope, receive, private_send if protected else send)


@asynccontextmanager
async def source_entry_read(knowledge, actor, tenant, identifiers, *, connections=None, version_id=None):
    """Admit exact origins before hydration, then revalidate before returning values."""
    reader = knowledge.source_reader.get() if knowledge.source_reader is not None else None
    if reader is None:
        yield
        return
    async with source_read_request(reader, actor, tenant, connections):
        operation = await reader.entries(actor, tenant, identifiers, version_id=version_id)
        async with operation.read_fence():
            yield
        await operation.release()
        async with operation.read_fence():
            pass


@asynccontextmanager
async def source_read_request(reader, actor, tenant, connections):
    operation = await reader.begin(actor, tenant, connections)
    snapshot = operation.selection
    with reader_source_snapshot(actor, tenant, snapshot):
        yield snapshot
        await reader.selections.confirm(actor, tenant, snapshot)


async def reader_response(reader, request: Request, tenant, body, read) -> Response:
    """Serialize under the exact request choice and make all controlled results private."""
    from koinon.knowledge.document_history.download_response import OriginalFileResponse

    value = None
    accepted = False
    try:
        actor = identity_from_request(request).subject
        async with source_read_request(reader, actor, tenant, body.reader_source_connections):
            value = await read(actor)
            response = (
                value if isinstance(value, Response) else JSONResponse(_json.dump_python(value, mode="json"))
            )
        accepted = True
    except SourceError as error:
        response = await source_problem(request, error)
    except Exception as error:
        response = await global_exception_handler(request, error)
    finally:
        if not accepted and isinstance(value, OriginalFileResponse):
            await value.download.close()
    response.headers.update(PRIVATE_HEADERS)
    return response
