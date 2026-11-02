# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextvars
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings, WorkAdmissionUnavailable
from koinon.workers.ingestion import IngestionDrain, pending_statement


async def test_saturated_tick_does_not_discover_or_claim_and_a_later_tick_can_run():
    gate = WorkAdmission(WorkAdmissionSettings(wait_timeout_seconds=0.01))
    worker = IngestionDrain(None, None, None, gate)
    worker._execute_one = AsyncMock()
    async with gate.hold("conversation"):
        await asyncio.create_task(worker.tick(), context=contextvars.Context())
    worker._execute_one.assert_not_awaited()
    assert gate.worker_active == gate.worker_waiting == 0
    await worker.tick()
    assert [call.args[0] for call in worker._execute_one.await_args_list] == ["canon", "structured"]


async def test_idle_domain_capacity_timeout_does_not_cancel_active_document_processing():
    gate = WorkAdmission(WorkAdmissionSettings(wait_timeout_seconds=0.01))
    worker = IngestionDrain(None, None, None, gate)
    started, release = asyncio.Event(), asyncio.Event()
    completed, cancelled = [], []

    async def execute(domain):
        started.set()
        try:
            await release.wait()
            completed.append(domain)
        except asyncio.CancelledError:
            cancelled.append(domain)
            raise

    worker._execute_one = execute
    task = asyncio.create_task(worker.tick())
    try:
        await started.wait()
        await asyncio.sleep(0.03)
        assert cancelled == [] and not task.done()
        release.set()
        await task
        assert completed == ["canon"]
        assert gate.worker_active == gate.worker_waiting == 0
    finally:
        release.set()
        await asyncio.gather(task, return_exceptions=True)


async def test_admitted_execution_capacity_error_is_not_hidden():
    worker = IngestionDrain(None, None, None, WorkAdmission(WorkAdmissionSettings()))
    worker._execute_one = AsyncMock(side_effect=WorkAdmissionUnavailable())
    with pytest.raises(WorkAdmissionUnavailable):
        await worker._one("canon")
    worker._execute_one.assert_awaited_once_with("canon")


async def test_shutdown_still_cancels_active_ingestion_and_releases_waiting_permits():
    gate = WorkAdmission(WorkAdmissionSettings())
    worker = IngestionDrain(None, None, None, gate)
    started = asyncio.Event()

    async def execute(domain):
        started.set()
        await asyncio.Event().wait()

    worker._execute_one = execute
    task = asyncio.create_task(worker.tick())
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert gate.worker_active == gate.worker_waiting == 0


async def test_pending_job_without_any_event_is_found_and_active_or_other_kind_is_not(tmp_path):
    registry = DataSourceRegistry.for_config(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'pending.db'}",
                            "ddl-auto": "none",
                        }
                    }
                }
            }
        )
    )
    metadata = sa.MetaData()
    table = sa.Table(
        "canon_ingest_jobs",
        metadata,
        sa.Column("id", sa.String),
        sa.Column("tenant_id", sa.String),
        sa.Column("workspace_id", sa.String),
        sa.Column("status", sa.String),
        sa.Column("kind", sa.String),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    async with registry.primary.engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(
            table.insert(),
            [
                dict(
                    id="no-event",
                    tenant_id="north",
                    workspace_id="one",
                    kind="ingest",
                    status="queued",
                    created_at=now,
                    started_at=None,
                ),
                dict(
                    id="active",
                    tenant_id="north",
                    workspace_id="one",
                    kind="ingest",
                    status="running",
                    created_at=now,
                    started_at=now,
                ),
                dict(
                    id="reindex",
                    tenant_id="north",
                    workspace_id="one",
                    kind="reindex",
                    status="queued",
                    created_at=now,
                    started_at=None,
                ),
            ],
        )
    try:
        async with registry.primary.engine.connect() as connection:
            found = (await connection.execute(pending_statement("canon", now, 600))).mappings().all()
        assert [row["id"] for row in found] == ["no-event"]
        assert set(found[0]) == {"id", "tenant_id", "workspace_id"}
    finally:
        await registry.close()
