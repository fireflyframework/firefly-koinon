# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from koinon.integrations.content_sources.errors import SourceError
from pyfly.security.context import SecurityContext
from pyfly.session.adapters.memory import InMemorySessionStore


async def test_source_consent_requires_live_same_native_session_not_bearer_or_pat():
    from koinon.integrations.content_sources.sessions import SourceBrowserSessions

    store = InMemorySessionStore()
    sessions = SourceBrowserSessions(store)
    valid = SecurityContext(user_id="alice", attributes={"iss": "issuer", "sub": "alice"})
    await store.save("browser-a", {"SECURITY_CONTEXT": valid}, 60)
    await sessions.require("issuer|alice", "browser-a")
    for owner, identifier in (("issuer|bob", "browser-a"), ("issuer|alice", "browser-b")):
        with pytest.raises(SourceError):
            await sessions.require(owner, identifier)
    await store.delete("browser-a")
    with pytest.raises(SourceError):
        await sessions.require("issuer|alice", "browser-a")
    for invalid in (
        SecurityContext(user_id="alice", attributes={"iss": "issuer", "sub": "other"}),
        SecurityContext(
            user_id="alice", attributes={"iss": "issuer", "sub": "alice", "koinon_token_id": "pat"}
        ),
        {"user_id": "alice", "iss": "issuer", "sub": "alice"},
    ):
        await store.save("browser-a", {"SECURITY_CONTEXT": invalid}, 60)
        with pytest.raises(SourceError):
            await sessions.require("issuer|alice", "browser-a")
