# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owner manifest freshness is pinned to identities, without re-reading unrelated sources."""

from datetime import UTC, datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot
from koinon.evidence.service import ConversationEvidence
from koinon.exports.dtos import MessageSelection


def test_manifest_identity_normalizes_database_hashes_and_timezones_but_binds_selection():
    from koinon.evidence.recorded_identity import manifest_identity_revision

    instant = datetime(2026, 11, 10, tzinfo=UTC)
    identity = ("thread", (b"hash", instant), {"selection": b"saved-revision-1"})
    same = (
        "thread",
        (memoryview(b"hash"), instant.astimezone(timezone(timedelta(hours=-8)))),
        {"selection": b"saved-revision-1"},
    )
    revision = manifest_identity_revision("actor", "tenant", "thread", ["b", "a"], identity)
    assert revision == manifest_identity_revision("actor", "tenant", "thread", ["a", "b"], same)
    assert revision != manifest_identity_revision("other", "tenant", "thread", ["a", "b"], identity)
    assert revision != manifest_identity_revision(
        "actor",
        "tenant",
        "thread",
        ["a", "b"],
        ("thread", (b"hash", instant), {"selection": b"saved-revision-2"}),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("changed", [False, True])
async def test_manifest_uses_identity_revision_and_rechecks_after_resolution(changed):
    snapshot = ConversationSnapshot(
        thread_id="thread",
        tenant_id="tenant",
        owner_subject="owner",
        title="Conversation",
        revision="b" * 64,
        messages=(
            ConversationMessage(
                id="message",
                role="user",
                text="Question",
                status="completed",
                revision="c" * 64,
            ),
        ),
        sources=(),
        source_manifest_complete=True,
    )
    calls = 0

    class Identities:
        async def revision(self, actor, tenant, thread, messages):
            nonlocal calls
            calls += 1
            return ("d" if changed and calls == 2 else "a") * 64

    class Snapshots:
        async def snapshot(self, *args):
            return snapshot

    class Access:
        async def check(self, *args, **kwargs):
            return None

    reviews = SimpleNamespace(
        snapshots=SimpleNamespace(get=lambda: Snapshots()),
        access=Access(),
        sources=SimpleNamespace(get=lambda: None),
    )
    service = ConversationEvidence(reviews, Identities())
    request = MessageSelection(thread_id="thread", message_ids=["message"])
    if changed:
        with pytest.raises(AccessDenied):
            await service.conversation("owner", "tenant", request)
    else:
        result = await service.conversation("owner", "tenant", request)
        assert result.revision == "a" * 64
        assert calls == 2
