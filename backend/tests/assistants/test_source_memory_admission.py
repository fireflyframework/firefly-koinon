# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Personal memory checks reader source authority before loading retained context."""

from types import SimpleNamespace

import pytest

from koinon.assistants.memory.service import PersonalConversationMemory
from koinon.integrations.content_sources.errors import SourceError


@pytest.mark.asyncio
async def test_queued_saved_baseline_cannot_cross_task_identity_or_lifetime():
    import asyncio
    from contextvars import copy_context

    from koinon.integrations.content_sources.read_context import (
        current_reader_snapshot,
        reader_source_snapshot,
    )
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionSnapshot, ReaderSourceSelection

    choice = ReaderSourceSelection(provider="google_drive", connection_id="reader")
    baseline = ReaderSelectionSnapshot((choice,), 3)

    async def read():
        return current_reader_snapshot("reader", "tenant", (choice,))

    with reader_source_snapshot("reader", "tenant", baseline):
        assert current_reader_snapshot("reader", "tenant", (choice,)) == baseline
        with pytest.raises(SourceError):
            await asyncio.create_task(read())
        with pytest.raises(SourceError):
            current_reader_snapshot("other", "tenant", (choice,))
        with pytest.raises(SourceError):
            current_reader_snapshot("reader", "tenant", ())
        copied = copy_context()
    with pytest.raises(SourceError):
        copied.run(current_reader_snapshot, "reader", "tenant", (choice,))


@pytest.mark.asyncio
async def test_native_begin_preserves_saved_revision_despite_frozen_explicit_choices():
    from unittest.mock import AsyncMock

    from koinon.integrations.content_sources.read_context import reader_source_snapshot
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionSnapshot, ReaderSourceSelection
    from koinon.integrations.content_sources.read_service import SourceReader

    choice = ReaderSourceSelection(provider="google_drive", connection_id="reader")
    baseline = ReaderSelectionSnapshot((choice,), 3)
    selections = SimpleNamespace(resolve=AsyncMock(), confirm=AsyncMock())
    reader = SourceReader(None, selections, None)
    with reader_source_snapshot("reader", "tenant", baseline):
        operation = await reader.begin("reader", "tenant", [choice])
        assert operation.selection == baseline
        selections.resolve.assert_not_awaited()
        selections.confirm.assert_awaited_once_with("reader", "tenant", baseline)
        selections.confirm.side_effect = SourceError("authority_changed")
        with pytest.raises(SourceError):
            await reader.begin("reader", "tenant", [choice])


@pytest.mark.asyncio
async def test_source_denial_precedes_memory_manifest_hydration():
    class Reader:
        async def runs(self, actor, tenant, identifiers):
            assert (actor, tenant, identifiers) == ("reader", "tenant", ("run",))
            raise SourceError("access_denied")

    class Repository:
        async def active_manifests(self, *args):
            pytest.fail("A denied stored manifest was hydrated")

    memory = PersonalConversationMemory.__new__(PersonalConversationMemory)
    memory.repository = Repository()
    memory.source_reader = SimpleNamespace(get=lambda: Reader())
    with pytest.raises(SourceError, match="access_denied"):
        await memory.authorize_many("reader", "tenant", ("run",))


@pytest.mark.asyncio
async def test_transferred_memory_checks_reader_connection_with_stored_owner_provenance():
    class Reader:
        async def runs(self, actor, tenant, identifiers, *, owner):
            assert (actor, tenant, identifiers, owner) == ("reader", "tenant", ("run",), "owner")
            raise SourceError("access_denied")

    class Repository:
        async def active_manifests(self, *args):
            pytest.fail("A transferred manifest was hydrated before reader authorization")

        async def result_context(self, *args):
            pytest.fail("A transferred result was hydrated before reader authorization")

    memory = PersonalConversationMemory.__new__(PersonalConversationMemory)
    memory.repository = Repository()
    memory.source_reader = SimpleNamespace(get=lambda: Reader())
    with pytest.raises(SourceError, match="access_denied"):
        await memory.authorize("owner", "tenant", "run", reader_subject="reader")
    with pytest.raises(SourceError, match="access_denied"):
        await memory.authorize_result("owner", "tenant", "run", "result", "a" * 64, reader_subject="reader")
