# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded JSON event parsing and explicit asynchronous connection ownership."""

import codecs
import json
import re
from collections.abc import AsyncGenerator, AsyncIterator
from types import TracebackType

import httpx

from koinon_sdk.models import StreamEvent

MAX_FRAME_BYTES = 1_048_576


class EventStream(AsyncIterator[StreamEvent]):
    def __init__(self, events: AsyncGenerator[StreamEvent, None]):
        self._events = events

    async def __aenter__(self) -> "EventStream":
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.aclose()

    def __aiter__(self) -> "EventStream":
        return self

    async def __anext__(self) -> StreamEvent:
        return await anext(self._events)

    async def aclose(self) -> None:
        await self._events.aclose()


async def read_events(response: httpx.Response) -> AsyncIterator[StreamEvent]:
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    buffer, event_id, event_type = "", "", "message"
    data: list[str] = []
    frame_bytes = 0

    async def chunks():
        async for chunk in response.aiter_bytes():
            yield decoder.decode(chunk), False
        yield decoder.decode(b"", final=True), True

    async for text, final in chunks():
        buffer += text
        while match := re.search(r"\r\n|\n|\r", buffer):
            if not final and match[0] == "\r" and match.end() == len(buffer):
                break
            line, buffer = buffer[: match.start()], buffer[match.end() :]
            frame_bytes += len(line.encode("utf-8"))
            if frame_bytes > MAX_FRAME_BYTES:
                raise ValueError("Event stream frame exceeds 1 MiB")
            if not line:
                if data:
                    yield StreamEvent(id=event_id, type=event_type, data=json.loads("\n".join(data)))
                data, event_type, frame_bytes = [], "message", 0
            elif not line.startswith(":"):
                field, _, value = line.partition(":")
                value = value[1:] if value.startswith(" ") else value
                if field == "data":
                    data.append(value)
                elif field == "event":
                    event_type = value or "message"
                elif field == "id" and "\0" not in value:
                    event_id = value
        if frame_bytes + len(buffer.encode("utf-8")) > MAX_FRAME_BYTES:
            raise ValueError("Event stream frame exceeds 1 MiB")
