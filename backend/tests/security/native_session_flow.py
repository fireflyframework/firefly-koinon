# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist callback challenges through the native session capability boundary."""

from pyfly.session.adapters.memory import InMemorySessionStore
from pyfly.session.filter import SessionFilter


class NativeSessionFlow:
    def __init__(self):
        self.store = InMemorySessionStore()
        self.filter = SessionFilter(self.store)

    async def persist_challenge(self, session):
        await self.store.save(session.id, session.get_data(), 60)

    async def callback(self, handler, request):
        request.scope["headers"] = [
            *request.scope["headers"],
            (b"cookie", f"PYFLY_SESSION={request.state.session.id}".encode()),
        ]
        return await self.filter.do_filter(request, handler)
