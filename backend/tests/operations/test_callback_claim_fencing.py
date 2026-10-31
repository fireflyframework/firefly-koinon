# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real SQLite proves reservations survive the claim transaction, without webhook I/O."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import sqlalchemy as sa
from flyquery.core.services.callbacks.callback_repository import CallbackOutboxRepository
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest.fixture
async def callback_rows(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'callbacks.db'}")

    # Original repository emits PG-only lock syntax. Removing that syntax lets
    # SQLite demonstrate the post-commit duplicate independently of row locks.
    @sa.event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
    def sqlite_syntax(connection, cursor, statement, parameters, context, executemany):
        return statement.replace("FOR UPDATE SKIP LOCKED", "").replace(
            "now()", "CURRENT_TIMESTAMP"
        ), parameters

    columns = [
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("ingest_job_id", sa.Uuid),
        sa.Column("tenant_id", sa.String),
        sa.Column("workspace_id", sa.Uuid),
        *[
            sa.Column(name, sa.String)
            for name in ("callback_url", "callback_secret", "event_type", "status", "last_error")
        ],
        sa.Column("callback_headers", sa.JSON),
        sa.Column("payload_json", sa.JSON),
        sa.Column("attempts", sa.Integer),
        sa.Column("last_status_code", sa.Integer),
        *[
            sa.Column(name, sa.DateTime(timezone=True))
            for name in ("last_attempt_at", "next_attempt_at", "created_at", "finished_at")
        ],
    ]
    table = sa.Table("flyquery_callback_outbox", sa.MetaData(), *columns)
    async with engine.begin() as connection:
        await connection.run_sync(table.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    identifier = uuid4()
    async with factory.begin() as session:
        await session.execute(
            table.insert().values(
                id=identifier,
                ingest_job_id=uuid4(),
                tenant_id="north",
                workspace_id=uuid4(),
                callback_url="https://callback.invalid/events",
                event_type="finished",
                status="PENDING",
                attempts=0,
                next_attempt_at=datetime.now(UTC) - timedelta(seconds=60),
                created_at=datetime.now(UTC),
                callback_headers={},
                payload_json={"status": "SUCCEEDED"},
            )
        )
    yield CallbackOutboxRepository(factory), table, factory, identifier
    await engine.dispose()


async def test_callback_claim_is_durable_and_blocks_peer_after_transaction_exit(callback_rows):
    repo, table, factory, identifier = callback_rows
    first = await repo.claim_due_batch(limit=1)
    assert len(first) == 1
    assert await repo.claim_due_batch(limit=1) == [], (
        "Peer must not claim a row already reserved for HTTP delivery"
    )
    async with factory() as session:
        row = (await session.execute(sa.select(table))).mappings().one()
        assert row["attempts"] == 0, "Reserving does not spend a completed delivery retry"
        assert row["next_attempt_at"] > datetime.now(UTC).replace(tzinfo=None)


async def test_expired_callback_owner_cannot_finalize_reclaimed_delivery(callback_rows):
    repo, table, factory, identifier = callback_rows
    old = (await repo.claim_due_batch(limit=1))[0]
    async with factory.begin() as session:
        await session.execute(table.update().values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1)))
    new = (await repo.claim_due_batch(limit=1))[0]
    assert new["last_attempt_at"] != old["last_attempt_at"]
    assert not await repo.mark_delivered(id_=identifier, status_code=200, claim=old)
    assert await repo.mark_delivered(id_=identifier, status_code=200, claim=new)
    async with factory() as session:
        row = (await session.execute(sa.select(table))).mappings().one()
        assert row["status"] == "DELIVERED" and row["attempts"] == 1


async def test_denied_managed_callback_sends_no_bytes_and_settles_dead(callback_rows, monkeypatch):
    from types import SimpleNamespace

    from flyquery.core.services.callbacks import callback_worker
    from flyquery.core.services.callbacks.callback_dispatcher import DeliveryOutcome
    from flyquery.data import workspace_scope

    repo, table, factory, identifier = callback_rows
    claim = (await repo.claim_due_batch(limit=1))[0]
    sent = []

    async def deliver(**arguments):
        sent.append(arguments["payload"])
        return DeliveryOutcome(success=True, status_code=200, error=None)

    async def deny(row):
        raise PermissionError("private credential details must not escape")

    monkeypatch.setattr(callback_worker, "deliver", deliver)
    worker = callback_worker.CallbackWorker(
        repo, SimpleNamespace(_require_model_bindings=True), SimpleNamespace()
    )
    worker._access = lambda: SimpleNamespace(authorize=deny)
    with workspace_scope(claim["tenant_id"], str(claim["workspace_id"])):
        await worker._dispatch(SimpleNamespace(), claim)
    assert sent == []
    async with factory() as session:
        row = (await session.execute(sa.select(table))).mappings().one()
        assert row["status"] == "DEAD" and row["attempts"] == 1
        assert "private credential" not in row["last_error"]


async def test_expired_reservation_sends_no_bytes_even_after_authority_passes(callback_rows, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from flyquery.core.services.callbacks import callback_worker
    from flyquery.data import workspace_scope

    repo, table, factory, identifier = callback_rows
    claim = (await repo.claim_due_batch(limit=1))[0]
    async with factory.begin() as session:
        await session.execute(table.update().values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1)))
    deliver = AsyncMock(side_effect=AssertionError("Expired callback sent outgoing bytes"))
    monkeypatch.setattr(callback_worker, "deliver", deliver)
    worker = callback_worker.CallbackWorker(
        repo, SimpleNamespace(_require_model_bindings=True), SimpleNamespace()
    )
    worker._access = lambda: SimpleNamespace(authorize=AsyncMock())
    with workspace_scope(claim["tenant_id"], str(claim["workspace_id"])):
        await worker._dispatch(SimpleNamespace(), claim)
    deliver.assert_not_awaited()


def _callback_process(database_url, result, hold):
    import asyncio
    import time

    async def claim():
        engine = create_async_engine(database_url)
        try:
            repository = CallbackOutboxRepository(async_sessionmaker(engine, expire_on_commit=False))
            rows = await repository.claim_due_batch(limit=1)
            result.send(rows)
        finally:
            await engine.dispose()

    asyncio.run(claim())
    result.close()
    if hold:
        time.sleep(30)


async def test_two_worker_processes_and_forced_termination_preserve_callback_reservation(callback_rows):
    import multiprocessing

    repository, table, factory, identifier = callback_rows
    process_context = multiprocessing.get_context("spawn")
    database_url = str(factory.kw["bind"].url)
    children = []

    def start(hold=False):
        receiving, sending = process_context.Pipe(duplex=False)
        process = process_context.Process(target=_callback_process, args=(database_url, sending, hold))
        process.start()
        sending.close()
        children.append(process)
        assert receiving.poll(10), "Worker did not report its durable claim"
        rows = receiving.recv()
        receiving.close()
        return process, rows

    try:
        first, old = start(hold=True)
        assert len(old) == 1
        peer, duplicate = start()
        peer.join(10)
        assert peer.exitcode == 0 and duplicate == []
        first.terminate()
        first.join(10)
        assert first.exitcode is not None and first.exitcode != 0
        async with factory.begin() as session:
            await session.execute(
                table.update().values(next_attempt_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        replacement, reclaimed = start()
        replacement.join(10)
        assert replacement.exitcode == 0 and len(reclaimed) == 1
        assert not await repository.mark_attempt_failure(
            id_=identifier,
            error="stale",
            status_code=None,
            backoff_seconds=60,
            terminal=False,
            claim=old[0],
        )
        assert await repository.mark_delivered(id_=identifier, status_code=200, claim=reclaimed[0])
    finally:
        for child in children:
            if child.is_alive():
                child.terminate()
            child.join(10)
