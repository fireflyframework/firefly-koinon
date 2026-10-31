# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import sqlalchemy as sa
from flyquery.core.services.ingestion import workers
from flyquery.core.services.ingestion.workers import IngestWorker
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


async def test_old_structured_worker_cannot_finish_replacement_attempt(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'attempts.db'}")

    @sa.event.listens_for(engine.sync_engine, "before_cursor_execute", retval=True)
    def sqlite_syntax(connection, cursor, statement, parameters, context, executemany):
        def converted(value):
            return value.hex if isinstance(value, UUID) else value

        values = (
            {key: converted(value) for key, value in parameters.items()}
            if isinstance(parameters, dict)
            else tuple(converted(value) for value in parameters)
        )
        return statement.replace("now()", "CURRENT_TIMESTAMP"), values

    columns = [
        *[
            sa.Column(name, sa.Uuid)
            for name in ("id", "workspace_id", "dataset_id", "table_id", "file_id", "snapshot_id")
        ],
        *[
            sa.Column(name, sa.String)
            for name in ("tenant_id", "job_kind", "status", "callback_url", "callback_secret")
        ],
        *[sa.Column(name, sa.JSON) for name in ("request_json", "result_json", "callback_headers")],
        sa.Column("attempts", sa.Integer),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    ]
    table = sa.Table("flyquery_ingest_jobs", sa.MetaData(), *columns)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(table.metadata.create_all)
    identifier, workspace = uuid4(), uuid4()
    async with factory.begin() as session:
        await session.execute(
            table.insert().values(
                id=identifier,
                tenant_id="north",
                workspace_id=workspace,
                dataset_id=uuid4(),
                job_kind="SAMPLE_REFRESH",
                status="PENDING",
                attempts=0,
                request_json={},
                callback_headers={},
            )
        )
    for name in ("emit_running", "emit_final", "emit_error"):
        monkeypatch.setattr(workers, name, AsyncMock())
    settings = SimpleNamespace(
        ingest_worker_concurrency=1,
        ingest_handler_timeout_s=10,
        ingest_shutdown_grace_s=1,
        processing_lease_s=60,
        ingest_max_attempts=3,
    )
    old, new = [
        IngestWorker(SimpleNamespace(), settings, factory, SimpleNamespace(), SimpleNamespace())
        for _ in range(2)
    ]
    old_entered, new_entered, release_old, release_new = [asyncio.Event() for _ in range(4)]

    async def first(**kwargs):
        old_entered.set()
        await release_old.wait()

    async def second(**kwargs):
        new_entered.set()
        await release_new.wait()

    old._run_stages, new._run_stages = first, second
    envelope = SimpleNamespace(
        payload={"ingest_job_id": str(identifier), "tenant_id": "north", "workspace_id": str(workspace)}
    )
    first_task = asyncio.create_task(old._handle_ingest_requested(envelope))
    await asyncio.wait_for(old_entered.wait(), 1)
    # Simulate expiry/reaper while the first provider call is suspended.
    async with factory.begin() as session:
        await session.execute(table.update().values(status="PENDING", started_at=None))
    second_task = asyncio.create_task(new._handle_ingest_requested(envelope))
    await asyncio.wait_for(new_entered.wait(), 1)
    try:
        release_old.set()
        await asyncio.wait_for(first_task, 1)
        async with factory() as session:
            row = (await session.execute(sa.select(table))).mappings().one()
            assert row["status"] == "RUNNING" and row["attempts"] == 2, "Old worker finalized a newer attempt"
    finally:
        release_old.set()
        release_new.set()
        await asyncio.gather(first_task, second_task, return_exceptions=True)
        await engine.dispose()
