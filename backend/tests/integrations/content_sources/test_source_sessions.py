# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.security.context import SecurityContext
from pyfly.session.adapters.memory import InMemorySessionStore

from koinon.integrations.content_sources.errors import SourceError


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


@pytest.mark.parametrize("invalid", [None, "missing", "naive", "past", "foreign"])
async def test_validation_uses_the_actual_session_deadline_without_extending_it(invalid):
    from koinon.integrations.content_sources.sessions import SourceBrowserSessions

    store = InMemorySessionStore()
    context = SecurityContext(user_id="alice", attributes={"iss": "issuer", "sub": "alice"})
    await store.save("browser", {"SECURITY_CONTEXT": context}, 90)
    deadline = datetime.now(UTC) + timedelta(seconds=90)
    observed = {"missing": None, "naive": datetime(2030, 1, 1), "past": datetime(2000, 1, 1, tzinfo=UTC)}
    store.expires_at = AsyncMock(return_value=observed.get(invalid, deadline))
    store.save = AsyncMock(side_effect=AssertionError("An expiry observation must not extend the session"))
    sessions = SourceBrowserSessions(store)
    if invalid is None:
        assert await sessions.require_with_expiry("issuer|alice", "browser") == deadline
    else:
        with pytest.raises(SourceError):
            await sessions.require_with_expiry(
                "issuer|bob" if invalid == "foreign" else "issuer|alice", "browser"
            )


async def test_validation_rejects_absent_expiry_and_logout_during_observation():
    from koinon.integrations.content_sources.sessions import SourceBrowserSessions

    context = SecurityContext(user_id="alice", attributes={"iss": "issuer", "sub": "alice"})
    snapshot = {"SECURITY_CONTEXT": context}
    unavailable = SourceBrowserSessions(SimpleNamespace(get=AsyncMock(return_value=snapshot)))
    with pytest.raises(SourceError):
        await unavailable.require_with_expiry("issuer|alice", "browser")
    changed = SourceBrowserSessions(
        SimpleNamespace(
            get=AsyncMock(side_effect=[snapshot, None]),
            expires_at=AsyncMock(return_value=datetime.now(UTC) + timedelta(seconds=90)),
        )
    )
    with pytest.raises(SourceError):
        await changed.require_with_expiry("issuer|alice", "browser")
