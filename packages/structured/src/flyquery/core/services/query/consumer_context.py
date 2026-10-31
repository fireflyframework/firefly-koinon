# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Server-bound execution context for consumers with additional retained-output authority."""

import json
from abc import ABC, abstractmethod
from contextlib import contextmanager
from contextvars import ContextVar

_context: ContextVar[dict | None] = ContextVar("structured_query_consumer_context", default=None)


@contextmanager
def bind_consumer_context(value: dict):
    encoded = json.dumps(value, allow_nan=False)
    if len(encoded.encode()) > 16384:
        raise ValueError("Query consumer context exceeds its bound")
    token = _context.set(json.loads(encoded))
    try:
        yield
    finally:
        _context.reset(token)


def consumer_context():
    value = _context.get()
    return json.loads(json.dumps(value)) if value is not None else None


class ConsumerQueryAccess(ABC):
    @abstractmethod
    async def authorize(self, contexts: tuple[dict, ...], tenant_id: str, workspace_id: str) -> None: ...
