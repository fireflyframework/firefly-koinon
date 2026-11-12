# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real PostgreSQL queue, expiry and checkpoint fencing with disposable storage."""

import asyncio
import importlib.util
import os
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from pyfly.data.relational.sqlalchemy import Base
from pyfly.kernel.exceptions import ConflictException
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from koinon.catalog.entities import Tenant
from koinon.integrations.content_sources.account_operation_dtos import (
    AccountOperationBusy,
    AccountOperationIdentity,
    AccountOperationLease,
    AccountOperationRequest,
)
from koinon.integrations.content_sources.account_operation_entities import (
    ACCOUNT_OPERATION_TABLES,
    SourceAccountOperation,
    SourceAccountWaiter,
)
from koinon.integrations.content_sources.account_operation_repository import SourceAccountOperationRepository

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture(scope="module", params=["migrated", "metadata"])
def account_database(request):
    uri = os.environ.get("KOINON_ACCOUNT_OPERATION_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires explicitly owned account-operation PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port == 55439
    name = "source_account_" + uuid4().hex[:12]
    target = base.set(database=name)
    engine = sa.create_engine(target.set(drivername="postgresql+psycopg"))
    with psycopg.connect(uri, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(name))
        )
    try:
        spec = importlib.util.spec_from_file_location("account_migrate", ROOT / "deploy/migrate.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.connect() as connection:
            config = module.history_config("native", ROOT / "deploy/migrations/native_versions", connection)
            command.upgrade(
                config,
                "koinon_0058_account_admission"
                if request.param == "migrated"
                else "koinon_0057_proof_indexes",
            )
            if request.param == "metadata":
                Base.metadata.create_all(connection, tables=list(ACCOUNT_OPERATION_TABLES))
            connection.commit()
        yield target
    finally:
        engine.dispose()
        with psycopg.connect(uri, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


@pytest.fixture
async def account_sessions(account_database):
    engine = create_async_engine(account_database.set(drivername="postgresql+asyncpg"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    tenant = "account_" + uuid4().hex[:12]
    async with sessions.begin() as session:
        session.add(Tenant(id=tenant, name="Account admission test"))
    try:
        yield sessions, AccountOperationIdentity(tenant_id=tenant, account_key=b"a" * 32)
    finally:
        await engine.dispose()


def operation(name, **changes):
    values = dict(
        kind="synchronization",
        operation_id=name,
        revision=1,
        generation=2,
        connection_id="connection",
        connection_revision=1,
        owner="owner",
        process_instance_id="worker",
    )
    return AccountOperationRequest.model_validate(values | changes)


async def acquire(sessions, identity, request):
    async with sessions.begin() as session:
        return await SourceAccountOperationRepository(session=session).try_acquire(identity, request)


async def test_fifo_retry_retains_ticket_and_new_slice_joins_tail(account_sessions):
    sessions, identity = account_sessions
    first = await acquire(sessions, identity, operation("first"))
    assert isinstance(first, AccountOperationLease)
    assert isinstance(await acquire(sessions, identity, operation("second")), AccountOperationBusy)
    assert isinstance(await acquire(sessions, identity, operation("third")), AccountOperationBusy)
    async with sessions.begin() as session:
        tickets = dict(
            (
                await session.execute(
                    sa.select(SourceAccountWaiter.operation_id, SourceAccountWaiter.ticket).where(
                        SourceAccountWaiter.tenant_id == identity.tenant_id
                    )
                )
            ).all()
        )
    assert isinstance(
        await acquire(sessions, identity, operation("second", process_instance_id="restarted")),
        AccountOperationBusy,
    )
    async with sessions.begin() as session:
        assert await SourceAccountOperationRepository(session=session).finish(first, outcome="clean")
    assert isinstance(await acquire(sessions, identity, operation("first", revision=2)), AccountOperationBusy)
    second = await acquire(sessions, identity, operation("second", process_instance_id="restarted"))
    assert isinstance(second, AccountOperationLease) and second.ticket == tickets["second"]
    assert second.fence > first.fence
    async with sessions.begin() as session:
        assert await SourceAccountOperationRepository(session=session).finish(second, outcome="clean")
    third = await acquire(sessions, identity, operation("third"))
    assert isinstance(third, AccountOperationLease) and third.ticket == tickets["third"]


async def test_duplicate_holder_never_returns_token_and_cancel_preserves_holder(account_sessions):
    sessions, identity = account_sessions
    request = operation("held")
    lease = await acquire(sessions, identity, request)
    duplicate = await acquire(sessions, identity, request)
    assert isinstance(duplicate, AccountOperationBusy)
    assert set(duplicate.model_dump()) == {"retry_after_seconds"}
    async with sessions.begin() as session:
        repository = SourceAccountOperationRepository(session=session)
        assert not await repository.cancel_waiter(identity, request)
        await repository.assert_current(lease)


@pytest.mark.parametrize(
    "field", ["token", "fence", "ticket", "generation", "connection_revision", "process_instance_id", "owner"]
)
async def test_forged_and_stale_lease_cannot_commit_or_release(account_sessions, field):
    sessions, identity = account_sessions
    lease = await acquire(sessions, identity, operation("held"))
    if field in {"token", "fence", "ticket"}:
        forged = lease.model_copy(update={field: uuid4() if field == "token" else getattr(lease, field) + 1})
    else:
        value = getattr(lease.operation, field)
        forged = lease.model_copy(
            update={
                "operation": lease.operation.model_copy(
                    update={field: value + 1 if isinstance(value, int) else value + "x"}
                )
            }
        )
    async with sessions.begin() as session:
        repository = SourceAccountOperationRepository(session=session)
        with pytest.raises(ConflictException, match="Account operation lease"):
            await repository.assert_current(forged)
        assert not await repository.finish(forged, outcome="clean")
        await repository.assert_current(lease)


async def test_uncertain_completion_quarantines_and_late_finish_cannot_shorten(account_sessions):
    sessions, identity = account_sessions
    lease = await acquire(sessions, identity, operation("held"))
    async with sessions.begin() as session:
        repository = SourceAccountOperationRepository(session=session)
        assert await repository.finish(lease, outcome="uncertain")
        row = await session.get(SourceAccountOperation, (identity.tenant_id, identity.account_key))
        assert row.quarantine_until == lease.expires_at + timedelta(seconds=30)
        assert not await repository.finish(lease, outcome="clean")
    assert isinstance(await acquire(sessions, identity, operation("next")), AccountOperationBusy)


async def test_expiry_keeps_quarantine_and_fence_survives_idle_header_eviction(account_sessions):
    sessions, identity = account_sessions
    lease = await acquire(sessions, identity, operation("held"))
    async with sessions.begin() as session:
        await session.execute(
            sa.text(
                "UPDATE koinon_source_account_operations "
                "SET started_at=statement_timestamp()-interval '151 seconds',"
                "expires_at=statement_timestamp()-interval '1 second' WHERE tenant_id=:tenant"
            ),
            {"tenant": identity.tenant_id},
        )
    assert isinstance(await acquire(sessions, identity, operation("next")), AccountOperationBusy)
    async with sessions.begin() as session:
        await session.execute(
            sa.text(
                "UPDATE koinon_source_account_operations "
                "SET quarantine_until=clock_timestamp()-interval '1 second' WHERE tenant_id=:tenant"
            ),
            {"tenant": identity.tenant_id},
        )
    fresh = await acquire(sessions, identity, operation("next"))
    assert isinstance(fresh, AccountOperationLease) and fresh.fence > lease.fence
    async with sessions.begin() as session:
        repository = SourceAccountOperationRepository(session=session)
        assert not await repository.finish(lease, outcome="clean")
        assert await repository.finish(fresh, outcome="clean")
        await repository.prune_expired(identity.tenant_id, limit=1000)
        assert await session.get(SourceAccountOperation, (identity.tenant_id, identity.account_key)) is None
    recreated = await acquire(sessions, identity, operation("recreated"))
    assert (
        isinstance(recreated, AccountOperationLease)
        and recreated.fence > fresh.fence
        and recreated.ticket > fresh.ticket
    )


async def test_cancel_requires_original_queued_connection_and_does_not_change_holder(account_sessions):
    sessions, identity = account_sessions
    held = await acquire(sessions, identity, operation("held"))
    request = operation("queued")
    await acquire(sessions, identity, request)
    async with sessions.begin() as session:
        repository = SourceAccountOperationRepository(session=session)
        assert not await repository.cancel_waiter(
            identity, request.model_copy(update={"connection_revision": 2})
        )
        assert await repository.cancel_waiter(identity, request)
        assert not await repository.cancel_waiter(identity, request)
        await repository.assert_current(held)


async def test_independent_connections_cannot_claim_same_account(account_sessions):
    sessions, identity = account_sessions
    results = await asyncio.gather(
        acquire(sessions, identity, operation("one")), acquire(sessions, identity, operation("two"))
    )
    assert sum(isinstance(value, AccountOperationLease) for value in results) == 1
    assert sum(isinstance(value, AccountOperationBusy) for value in results) == 1


async def test_account_capacity_blocks_sixty_fifth_waiter_without_losing_oldest(account_sessions):
    sessions, identity = account_sessions
    lease = await acquire(sessions, identity, operation("held"))
    for index in range(63):
        assert isinstance(
            await acquire(sessions, identity, operation(f"queued-{index}")), AccountOperationBusy
        )
    assert isinstance(await acquire(sessions, identity, operation("overflow")), AccountOperationBusy)
    async with sessions.begin() as session:
        assert (
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(SourceAccountWaiter)
                .where(SourceAccountWaiter.tenant_id == identity.tenant_id)
            )
            == 64
        )
        assert await SourceAccountOperationRepository(session=session).finish(lease, outcome="clean")
    next_lease = await acquire(sessions, identity, operation("queued-0"))
    assert isinstance(next_lease, AccountOperationLease)


def test_identity_queue_plans_use_indexes(account_database):
    # Production-shaped many-tenant data without disabling sequential scans.
    prefix = "plans_" + uuid4().hex[:8]
    engine = sa.create_engine(account_database.set(drivername="postgresql+psycopg"))
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.insert(Tenant), [{"id": f"{prefix}_{n}", "name": "Plan tenant"} for n in range(20)]
            )
    finally:
        engine.dispose()
    with psycopg.connect(str(account_database)) as connection:
        connection.execute(
            "INSERT INTO koinon_source_account_operations(tenant_id,account_key,last_used_at) "
            "SELECT %s||'_'||(i/1000)::text,sha256(convert_to(i::text,'UTF8')),clock_timestamp() "
            "FROM generate_series(0,19999) i",
            (prefix,),
        )
        connection.execute(
            "INSERT INTO koinon_source_account_waiters(tenant_id,account_key,operation_kind,operation_id,"
            "continuation_revision,generation,ticket,connection_id,connection_revision,owner,"
            "last_requested_at,idle_expires_at) "
            "SELECT tenant_id,account_key,'validation','queue',1,0,"
            "nextval('koinon_source_account_ticket_seq'),'connection',1,'owner',"
            "statement_timestamp(),statement_timestamp()+interval '120 seconds' "
            "FROM koinon_source_account_operations WHERE tenant_id LIKE %s",
            (prefix + "_%",),
        )
        connection.execute("ANALYZE koinon_source_account_waiters")
        plan = connection.execute(
            "EXPLAIN SELECT ticket FROM koinon_source_account_waiters "
            "WHERE tenant_id=%s AND account_key=sha256(convert_to('0','UTF8')) ORDER BY ticket LIMIT 1",
            (prefix + "_0",),
        ).fetchall()
        assert any("Index" in row[0] for row in plan), plan
        expiry = connection.execute(
            "EXPLAIN SELECT ticket FROM koinon_source_account_waiters "
            "WHERE tenant_id=%s AND idle_expires_at<clock_timestamp() "
            "ORDER BY idle_expires_at,ticket LIMIT 64",
            (prefix + "_0",),
        ).fetchall()
        assert any("Index" in row[0] for row in expiry), expiry


@pytest.mark.parametrize(
    ("table", "assignment", "constraint"),
    [
        ("koinon_source_account_operations", "account_key=decode('00','hex')", "ck_account_operation_key"),
        ("koinon_source_account_operations", "token=NULL", "ck_account_operation_complete"),
        (
            "koinon_source_account_operations",
            "expires_at=started_at+interval '151 seconds'",
            "ck_account_operation_deadline",
        ),
        ("koinon_source_account_waiters", "account_key=decode('00','hex')", "ck_account_waiter_key"),
        (
            "koinon_source_account_waiters",
            "idle_expires_at=last_requested_at+interval '121 seconds'",
            "ck_account_waiter_idle",
        ),
    ],
)
async def test_postgres_metadata_keeps_account_constraints(account_sessions, table, assignment, constraint):
    sessions, identity = account_sessions
    lease = await acquire(sessions, identity, operation("held"))
    async with sessions.begin() as session:
        with pytest.raises(sa.exc.IntegrityError) as error:
            async with session.begin_nested():
                # Identifiers and expressions come only from the fixed cases above.
                await session.execute(
                    sa.text(f"UPDATE {table} SET {assignment} WHERE tenant_id=:tenant"),
                    {"tenant": identity.tenant_id},
                )
        assert constraint in str(error.value.orig)
        await SourceAccountOperationRepository(session=session).assert_current(lease)


async def test_checkpoint_and_release_rollback_together(account_sessions):
    sessions, identity = account_sessions
    lease = await acquire(sessions, identity, operation("held"))
    with pytest.raises(RuntimeError, match="forced checkpoint rollback"):
        async with sessions.begin() as session:
            repository = SourceAccountOperationRepository(session=session)
            await repository.assert_current(lease)
            assert await repository.finish(lease, outcome="clean")
            raise RuntimeError("forced checkpoint rollback")
    async with sessions.begin() as session:
        await SourceAccountOperationRepository(session=session).assert_current(lease)


async def test_expired_queued_ticket_can_be_pruned_without_removing_holder(account_sessions):
    sessions, identity = account_sessions
    held = await acquire(sessions, identity, operation("held"))
    await acquire(sessions, identity, operation("abandoned"))
    async with sessions.begin() as session:
        await session.execute(
            sa.text(
                "UPDATE koinon_source_account_waiters "
                "SET last_requested_at=statement_timestamp()-interval '121 seconds',"
                "idle_expires_at=statement_timestamp()-interval '1 second' WHERE tenant_id=:tenant"
            ),
            {"tenant": identity.tenant_id},
        )
        repository = SourceAccountOperationRepository(session=session)
        assert await repository.prune_expired(identity.tenant_id, limit=1) == 1
        await repository.assert_current(held)
        assert (
            await session.scalar(
                sa.select(sa.func.count())
                .select_from(SourceAccountWaiter)
                .where(SourceAccountWaiter.tenant_id == identity.tenant_id)
            )
            == 1
        )


async def test_tenant_capacity_and_cross_tenant_independence(account_sessions):
    sessions, identity = account_sessions
    async with sessions.begin() as session:
        await session.execute(
            sa.text(
                "INSERT INTO koinon_source_account_operations(tenant_id,account_key,last_used_at) "
                "SELECT :tenant,sha256(convert_to(i::text,'UTF8')),clock_timestamp() "
                "FROM generate_series(1,1000) i"
            ),
            {"tenant": identity.tenant_id},
        )
        await session.execute(
            sa.text(
                "INSERT INTO koinon_source_account_waiters(tenant_id,account_key,operation_kind,operation_id,"
                "continuation_revision,generation,ticket,connection_id,connection_revision,owner,"
                "last_requested_at,idle_expires_at) "
                "SELECT tenant_id,account_key,'validation','waiting',1,0,"
                "nextval('koinon_source_account_ticket_seq'),'connection',1,'owner',"
                "statement_timestamp(),statement_timestamp()+interval '120 seconds' "
                "FROM koinon_source_account_operations WHERE tenant_id=:tenant"
            ),
            {"tenant": identity.tenant_id},
        )
    assert isinstance(await acquire(sessions, identity, operation("overflow")), AccountOperationBusy)
    other = identity.model_copy(update={"tenant_id": identity.tenant_id + "_other"})
    async with sessions.begin() as session:
        session.add(Tenant(id=other.tenant_id, name="Other tenant"))
    assert isinstance(await acquire(sessions, other, operation("allowed")), AccountOperationLease)


def test_schema_rejects_partial_identity_and_sequences_never_cycle(account_database):
    tenant = "constraints_" + uuid4().hex[:12]
    engine = sa.create_engine(account_database.set(drivername="postgresql+psycopg"))
    try:
        with engine.begin() as connection:
            connection.execute(sa.insert(Tenant).values(id=tenant, name="Constraint tenant"))
    finally:
        engine.dispose()
    with psycopg.connect(str(account_database)) as connection:
        for key, token in ((b"short", None), (b"a" * 32, uuid4())):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    "INSERT INTO koinon_source_account_operations(tenant_id,account_key,token,last_used_at) "
                    "VALUES(%s,%s,%s,clock_timestamp())",
                    (tenant, key, token),
                )
        for sequence in ("koinon_source_account_fence_seq", "koinon_source_account_ticket_seq"):
            assert connection.execute(
                "SELECT seqcycle FROM pg_sequence WHERE seqrelid=%s::regclass", (sequence,)
            ).fetchone() == (False,)
