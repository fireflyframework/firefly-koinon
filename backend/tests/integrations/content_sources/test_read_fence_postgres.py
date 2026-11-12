# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Local source locks serialize disconnects without provider I/O in transactions."""

import asyncio

import pytest
from sqlalchemy import text
from test_source_concurrency_postgres import OWNER, TENANT, wait_for_blocked_connection
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import source_database as source_database

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.integrations.content_sources.repositories import SourceConnectionRepository

pytestmark = pytest.mark.integration


async def test_reader_connection_lock_covers_local_commit(source_sessions):
    sessions, uri = source_sessions
    async with sessions() as first, sessions() as second:
        reader = SourceReadRepository(session=first)
        comparison = await reader.check_connections(OWNER, TENANT, {"connection": 1})
        await reader.lock_origins(TENANT, (), comparison)
        assert await reader.check_connections(OWNER, TENANT, {"connection": 1}) == comparison
        await second.execute(text("SET LOCAL application_name='reader-fence-disconnect'"))
        pending = asyncio.create_task(
            SourceConnectionRepository(session=second).disconnect(TENANT, OWNER, "connection", 1)
        )
        try:
            await wait_for_blocked_connection(uri, "reader-fence-disconnect")
            assert not pending.done()
            await first.commit()
            assert await asyncio.wait_for(pending, 5)
            await second.commit()
        finally:
            if not pending.done():
                pending.cancel()
                await asyncio.gather(pending, return_exceptions=True)
    async with sessions() as check:
        with pytest.raises(SourceError, match="authority_changed"):
            await SourceReadRepository(session=check).check_connections(OWNER, TENANT, {"connection": 1})


async def test_disconnect_committed_before_fence_invalidates_comparison(source_sessions):
    sessions, _ = source_sessions
    async with sessions() as before:
        comparison = await SourceReadRepository(session=before).check_connections(
            OWNER, TENANT, {"connection": 1}
        )
    async with sessions.begin() as disconnected:
        assert await SourceConnectionRepository(session=disconnected).disconnect(
            TENANT, OWNER, "connection", 1
        )
    async with sessions() as write:
        reader = SourceReadRepository(session=write)
        await reader.lock_origins(TENANT, (), comparison)
        with pytest.raises(SourceError, match="authority_changed"):
            await reader.check_connections(OWNER, TENANT, {"connection": 1})
        await write.rollback()
