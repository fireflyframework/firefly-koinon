# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native SQLite activity persistence; external providers and databases are forbidden."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.kernel import DataIntegrityException
from sqlalchemy import event, func, select, text
from sqlalchemy.exc import IntegrityError

from koinon.activity.dtos import ActivityWindow
from koinon.activity.entities import ActivityCoverageState, ActivityEvent
from koinon.activity.observations import McpObservation
from koinon.activity.ports import ActivityObservationRecorder
from koinon.activity.repositories import ActivityEventRepository
from koinon.catalog.entities import Tenant
from koinon.catalog.repositories import TenantRepository


@pytest.fixture
async def activity(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'activity.db'}",
                            "read-replica": {"url": f"sqlite+aiosqlite:///{tmp_path / 'empty-replica.db'}"},
                            "datasources": {
                                "business": {
                                    "url": f"sqlite+aiosqlite:///{tmp_path / 'business.db'}",
                                    "ddl-auto": "none",
                                }
                            },
                        }
                    },
                }
            }
        )
    )
    for package in ("koinon.catalog", "koinon.activity"):
        scan_package(package, context.container)
    await context.start()
    try:
        for tenant in ("north", "south"):
            await context.get_bean(TenantRepository).save(Tenant(id=tenant, name=tenant))
        yield (
            context.get_bean(ActivityObservationRecorder),
            context.get_bean(ActivityEventRepository),
            context,
        )
    finally:
        await context.stop()


def observation(**changes):
    return McpObservation.model_validate(
        {
            "observation_id": uuid4(),
            "tenant_id": "north",
            "subject": "issuer|owner",
            "kind": "tool",
            "operation": "koinon_context",
            "outcome": "succeeded",
            "duration_ms": 1,
            **changes,
        }
    )


async def window(repo):
    now = await repo.database_now()
    return ActivityWindow(start_at=now - timedelta(days=1), end_at=now + timedelta(days=1), time_zone="UTC")


async def test_native_di_idempotent_concurrent_insert_and_db_clock_coverage(activity):
    service, repo, context = activity
    value = observation()
    await asyncio.gather(*(service.record_mcp(value) for _ in range(6)))
    engine = context.get_bean(DataSourceRegistry).engine()
    async with engine.connect() as connection:
        rows = (await connection.execute(select(ActivityEvent))).all()
        count = await connection.scalar(select(func.count()).select_from(ActivityCoverageState))
    assert len(rows) == count == 1
    assert rows[0].id == str(value.observation_id)
    first = await repo.coverage_started_at()
    assert first is not None and first.tzinfo is not None
    await service.record_mcp(observation())
    assert await repo.coverage_started_at() == first
    assert abs(((await repo.database_now()) - rows[0].created_at).total_seconds()) < 5


async def test_conflicting_uuid_cannot_overwrite_original_or_poison_next_observation(activity):
    service, repo, _ = activity
    value = observation()
    await service.record_mcp(value)
    with pytest.raises(Exception, match="differs"):
        await service.record_mcp(observation(observation_id=value.observation_id, duration_ms=999))
    await service.record_mcp(observation(duration_ms=3))
    result = await repo.aggregate("north", "issuer|owner", await window(repo), None)
    assert result.tool_calls.value == 2 and result.average_duration_ms.value == 2


async def test_sql_bounded_exact_tool_percentile_and_separate_request_outcomes(activity):
    service, repo, context = activity
    for number in range(1, 24):
        await service.record_mcp(
            observation(
                duration_ms=number,
                workspace_id="workspace" if number <= 20 else None,
                outcome="succeeded" if number <= 20 else ["cancelled", "failed", "rejected"][number - 21],
            )
        )
    for outcome in ("succeeded", "failed", "rejected", "cancelled"):
        await service.record_mcp(
            observation(kind="request", operation="POST", outcome=outcome, duration_ms=800000)
        )
    await service.record_mcp(observation(tenant_id="south", duration_ms=70000))
    await service.record_mcp(observation(subject="issuer|other", duration_ms=60000))
    statements = []
    engine = context.get_bean(DataSourceRegistry).engine()

    def capture(conn, cursor, statement, parameters, ctx, many):
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        result = await repo.aggregate("north", "issuer|owner", await window(repo), None)
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    assert result.tool_calls.value == 23 and result.requests.value == 4
    assert (
        result.succeeded.value,
        result.failed.value,
        result.rejected.value,
        result.tool_cancelled.value,
    ) == (20, 1, 1, 1)
    assert all(
        getattr(result, "request_" + outcome).value == 1
        for outcome in ("succeeded", "failed", "rejected", "cancelled")
    )
    assert result.average_duration_ms.value == 12 and result.p95_duration_ms.value == 22
    assert any("avg(" in sql.lower() and "sum(" in sql.lower() for sql in statements)
    assert any("ORDER BY" in sql and "LIMIT" in sql and "OFFSET" in sql for sql in statements)
    scoped = await repo.aggregate("north", "issuer|owner", await window(repo), ("workspace",))
    assert scoped.tool_calls.value == 20 and scoped.requests.value == 0
    assert scoped.average_duration_ms.value == 11 and scoped.p95_duration_ms.value == 19
    empty = await repo.aggregate("north", "issuer|owner", await window(repo), ())
    assert empty.tool_calls.value == 0 and empty.p95_duration_ms.status == "unavailable"


@pytest.mark.parametrize("table", ["koinon_activity_events", "koinon_activity_coverage"])
@pytest.mark.parametrize("mutation", ["DELETE FROM {table}", "UPDATE {table} SET {column} = {column}"])
async def test_sqlite_append_only_database_guards_reject_raw_mutations(activity, table, mutation):
    service, repo, context = activity
    await service.record_mcp(observation())
    column = "duration_ms" if table.endswith("events") else "coverage_started_at"
    engine = context.get_bean(DataSourceRegistry).engine()
    with pytest.raises(IntegrityError, match="append-only"):
        async with engine.begin() as connection:
            await connection.execute(text(mutation.format(table=table, column=column)))
    assert (await repo.aggregate("north", "issuer|owner", await window(repo), None)).tool_calls.value == 1


async def test_migration_initializes_db_coverage_and_guards_match_runtime_schema(tmp_path):
    import importlib.util
    from pathlib import Path

    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from sqlalchemy.ext.asyncio import create_async_engine

    path = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/native_versions/0031_activity_observations.py"
    )
    spec = importlib.util.spec_from_file_location("activity_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "koinon_0031_activity" and module.down_revision == "koinon_0030_comms"
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'migration.db'}")

    def migrate(connection):
        from pyfly.data.relational.sqlalchemy import Base

        for table in Base.metadata.sorted_tables:
            if table.name not in {"koinon_activity_events", "koinon_activity_coverage"}:
                table.create(connection)
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(migrate)
        async with engine.connect() as connection:
            assert await connection.scalar(select(func.count()).select_from(ActivityCoverageState)) == 1
            assert await connection.scalar(select(ActivityCoverageState.coverage_started_at)) is not None
            columns = (await connection.execute(text("PRAGMA table_info(koinon_activity_events)"))).all()
            assert {column[1] for column in columns} == set(ActivityEvent.__table__.columns.keys())
        with pytest.raises(IntegrityError, match="append-only"):
            async with engine.begin() as connection:
                await connection.execute(text("DELETE FROM koinon_activity_coverage"))
    finally:
        await engine.dispose()


def test_postgresql_runtime_guard_ddl_prohibits_rows_and_truncate_without_postgres():
    from sqlalchemy import create_mock_engine

    statements = []
    engine = create_mock_engine("postgresql://", lambda sql, *args, **kwargs: statements.append(str(sql)))
    ActivityEvent.__table__.create(engine)
    ActivityCoverageState.__table__.create(engine)
    assert sum("BEFORE UPDATE OR DELETE" in sql for sql in statements) == 2
    assert sum("BEFORE TRUNCATE" in sql for sql in statements) == 2
    assert sum("RAISE EXCEPTION" in sql and "append-only" in sql for sql in statements) == 2


async def test_aggregate_and_coverage_use_primary_even_when_replica_is_empty(activity):
    service, repo, context = activity
    await service.record_mcp(observation())
    registry = context.get_bean(DataSourceRegistry)
    async with registry.replica().engine.connect() as connection:
        exists = await connection.scalar(
            text("SELECT name FROM sqlite_master WHERE name = 'koinon_activity_events'")
        )
        if exists:
            assert await connection.scalar(select(func.count()).select_from(ActivityEvent)) == 0
    result = await repo.aggregate("north", "issuer|owner", await window(repo), None)
    assert result.tool_calls.value == 1 and await repo.coverage_started_at() is not None


async def test_failed_requires_new_observation_does_not_poison_caller_business_writer(activity):
    from pyfly.data.transaction import TransactionTemplate

    service, repo, context = activity
    registry = context.get_bean(DataSourceRegistry)
    async with registry.engine("business").begin() as connection:
        await connection.execute(text("CREATE TABLE caller_business (id INTEGER PRIMARY KEY)"))
    async with TransactionTemplate("business").transaction() as caller:
        await caller.resource.execute(text("INSERT INTO caller_business (id) VALUES (1)"))
        with pytest.raises(DataIntegrityException, match="foreign key"):
            await service.record_mcp(observation(tenant_id="missing-tenant"))
        assert caller.resource.is_active
        await caller.resource.execute(text("INSERT INTO caller_business (id) VALUES (2)"))
    async with registry.engine("business").connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM caller_business")) == 2
    assert (await repo.aggregate("north", "issuer|owner", await window(repo), None)).tool_calls.value == 0


async def test_native_observer_timeout_rolls_back_and_preserves_outward_success_counter(
    activity, monkeypatch
):
    from time import monotonic

    from test_mcp_activity_observations import Metrics, scope

    from koinon.mcp.observations import observe

    service, repo, context = activity
    original = repo.append

    async def slow(observation):
        await original(observation)
        await asyncio.sleep(5)

    monkeypatch.setattr(repo, "append", slow)
    metrics = Metrics()
    started = monotonic()
    await observe(scope(), "tool", "koinon_context", "succeeded", started, lambda: service, lambda: metrics)
    assert 1.5 <= monotonic() - started < 4
    assert metrics.calls[-1] == "inc"
    assert (await repo.aggregate("north", "issuer|owner", await window(repo), None)).tool_calls.value == 0
    assert await repo.coverage_started_at() is None
    monkeypatch.setattr(repo, "append", original)
    await service.record_mcp(observation())
    assert (await repo.aggregate("north", "issuer|owner", await window(repo), None)).tool_calls.value == 1
