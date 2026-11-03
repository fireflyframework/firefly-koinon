# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned PostgreSQL qualification of statement-level authority invalidation."""

import asyncio
from contextvars import Context
from uuid import uuid4

import psycopg
import pytest
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from sqlalchemy import inspect, text

from koinon.organization_knowledge.transitions.generation_schema_v1 import WATCHED
from koinon.organization_knowledge.transitions.generations import ModeGenerationRepository
from koinon.security.authority import primary_authority

pytest_plugins = ("test_index_publication_postgres",)
pytestmark = pytest.mark.integration


async def test_primary_generation_schema_covers_registered_semantic_columns(pg_indexes):
    engine = pg_indexes.get_bean(DataSourceRegistry).primary.engine
    async with engine.connect() as connection:

        def check(sync):
            inspector = inspect(sync)
            for table, (_, fields) in WATCHED.items():
                assert set(fields) <= {column["name"] for column in inspector.get_columns(table)}, table

        await connection.run_sync(check)


async def test_primary_statement_epoch_changes_once_and_rolls_back_with_journal(pg_indexes):
    repository = ModeGenerationRepository()
    before = await repository.current("tenant")
    async with primary_authority(read_only=False):
        session = repository._require_session()
        await session.execute(text("UPDATE lattice_catalog SET status='archived' WHERE tenant_id='tenant'"))
    assert await repository.current("tenant") == before + 1
    assert [
        (row.generation, row.workspace_id)
        for row in await repository.changes("tenant", after_generation=before)
    ] == [(before + 1, "workspace")]
    with pytest.raises(RuntimeError, match="controlled rollback"):
        async with primary_authority(read_only=False):
            await repository._require_session().execute(
                text("UPDATE lattice_catalog SET status='ready' WHERE tenant_id='tenant'")
            )
            assert await repository.current("tenant") == before + 1
            raise RuntimeError("controlled rollback")
    assert await repository.current("tenant") == before + 1
    assert await repository.changes("tenant", after_generation=before + 1) == []
    async with primary_authority(read_only=False):
        await repository._require_session().execute(
            text("UPDATE lattice_catalog SET name='Observed rename' WHERE tenant_id='tenant'")
        )
    assert await repository.current("tenant") == before + 1


async def test_primary_generation_share_fence_blocks_writer_until_commit(pg_indexes, record_property):
    repository = ModeGenerationRepository()
    datasource = pg_indexes.get_bean(DataSourceRegistry).primary
    uri = datasource.engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    application = "mode-generation-" + uuid4().hex
    started, finished = asyncio.Event(), asyncio.Event()

    async def mutate():
        async with await psycopg.AsyncConnection.connect(uri, application_name=application) as connection:
            started.set()
            await connection.execute("UPDATE lattice_catalog SET status='archived' WHERE id='workspace'")
        finished.set()

    running = None
    try:
        async with primary_authority(read_only=False):
            before = await repository.current("tenant", lock=True)
            running = asyncio.create_task(mutate(), context=Context())
            await asyncio.wait_for(started.wait(), 5)
            async with await psycopg.AsyncConnection.connect(uri, autocommit=True) as inspection:
                async with asyncio.timeout(5):
                    while True:
                        result = await inspection.execute(
                            "SELECT wait_event_type FROM pg_stat_activity WHERE application_name=%s",
                            (application,),
                        )
                        if await result.fetchone() == ("Lock",):
                            break
                        await asyncio.sleep(0.01)
            assert not finished.is_set()
            assert await repository.current("tenant") == before
        await asyncio.wait_for(running, 5)
        assert finished.is_set() and await repository.current("tenant") == before + 1
        record_property("writer_blocked_until_primary_commit", True)
    finally:
        if running is not None and not running.done():
            running.cancel()
        if running is not None:
            await asyncio.gather(running, return_exceptions=True)


async def test_primary_epoch_is_deferred_until_all_content_row_locks_are_acquired(pg_indexes):
    datasource = pg_indexes.get_bean(DataSourceRegistry).primary
    uri = datasource.engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    async with (
        await psycopg.AsyncConnection.connect(uri) as first,
        await psycopg.AsyncConnection.connect(uri) as second,
    ):
        before = (
            await (
                await first.execute(
                    "SELECT generation FROM koinon_knowledge_readiness_generations WHERE tenant_id='tenant'"
                )
            ).fetchone()
        )[0]
        await first.execute("UPDATE koinon_providers SET revision=revision+1 WHERE id='provider'")
        during = (
            await (
                await first.execute(
                    "SELECT generation FROM koinon_knowledge_readiness_generations WHERE tenant_id='tenant'"
                )
            ).fetchone()
        )[0]
        assert during == before, "Content statements must not acquire the shared generation row before commit"
        await second.execute("SET LOCAL lock_timeout='1000ms'")
        await second.execute("UPDATE lattice_catalog SET status='archived' WHERE id='workspace'")
        await second.commit()
        # The first transaction may continue editing content after the other has committed.
        await first.execute("UPDATE lattice_catalog SET status='ready' WHERE id='workspace'")
        await first.commit()
        after = (
            await (
                await first.execute(
                    "SELECT generation FROM koinon_knowledge_readiness_generations WHERE tenant_id='tenant'"
                )
            ).fetchone()
        )[0]
        assert after == before + 2
        assert (
            await (await first.execute("SELECT count(*) FROM koinon_knowledge_readiness_pending")).fetchone()
        )[0] == 0


async def test_final_fence_rejects_its_own_uncommitted_authority_changes(pg_indexes):
    repository = ModeGenerationRepository()
    before = await repository.current("tenant")
    async with primary_authority(read_only=False):
        assert await repository.matches("tenant", before)
    async with primary_authority(read_only=False):
        await repository._require_session().execute(
            text("UPDATE lattice_memberships SET active=false WHERE id='actor'")
        )
        assert await repository.current("tenant") == before
        assert not await repository.matches("tenant", before)
    assert await repository.current("tenant") == before + 1


async def test_early_constraint_flush_rejects_further_content_before_row_lock(pg_indexes):
    datasource = pg_indexes.get_bean(DataSourceRegistry).primary
    uri = datasource.engine.url.set(drivername="postgresql").render_as_string(hide_password=False)
    async with (
        await psycopg.AsyncConnection.connect(uri) as first,
        await psycopg.AsyncConnection.connect(uri) as second,
    ):
        await first.execute("UPDATE koinon_providers SET revision=revision+1 WHERE id='provider'")
        await first.execute("SET CONSTRAINTS ALL IMMEDIATE")
        await second.execute("SELECT id FROM lattice_catalog WHERE id='workspace' FOR UPDATE")
        await first.execute("SET LOCAL lock_timeout='1000ms'")
        with pytest.raises(psycopg.Error) as failure:
            await first.execute("UPDATE lattice_catalog SET status='archived' WHERE id='workspace'")
        assert failure.value.sqlstate == "25000"
        await first.rollback()
        await second.rollback()


async def test_index_parent_link_invalidates_at_commit_without_job_polling_churn(pg_indexes):
    from koinon.jobs.repository import JobRepository
    from koinon.jobs.service import JobService

    repository = ModeGenerationRepository()
    jobs = JobService(JobRepository())
    before = await repository.current("tenant")
    await jobs.submit("tenant", "workspace", "knowledge.mode", {}, "mode-parent")
    assert await repository.current("tenant") == before
    child = await jobs.submit(
        "tenant", "workspace", "knowledge.index", {"parent_mode_transition_id": "first"}, "index-child"
    )
    assert await repository.current("tenant") == before + 1
    child.status, child.progress = "running", 50
    await jobs.repository.save(child)
    assert await repository.current("tenant") == before + 1
    child.payload = {"parent_mode_transition_id": "second"}
    await jobs.repository.save(child)
    assert await repository.current("tenant") == before + 2
    child.kind = "unrelated"
    await jobs.repository.save(child)
    assert await repository.current("tenant") == before + 3
