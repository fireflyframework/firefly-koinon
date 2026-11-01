# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from koinon.workers.observations import bulk_queue_specifications, queue_statement


@pytest.mark.parametrize("kind", ["bulk_intake", "bulk_query"])
async def test_bulk_metric_matches_due_claims_cleanup_and_keeps_cancelled_live_work(kind, tmp_path):
    engine = create_async_engine("sqlite+aiosqlite:///" + str(tmp_path / "queue.db"))
    now = datetime.now(UTC)
    metadata = sa.MetaData()
    jobs = sa.Table(
        "lattice_jobs",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("kind", sa.String),
        sa.Column("status", sa.String),
        sa.Column("available_at", sa.DateTime(timezone=True)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("attempts", sa.Integer),
        sa.Column("max_attempts", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    batches = sa.Table(
        "koinon_bulk_batches" if kind == "bulk_intake" else "koinon_query_batches",
        metadata,
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("cancelled", sa.Boolean),
    )
    items = sa.Table(
        "koinon_bulk_items" if kind == "bulk_intake" else "koinon_query_batch_items",
        metadata,
        sa.Column("job_id", sa.String),
        sa.Column("batch_id", sa.String),
        sa.Column("status", sa.String),
    )
    values = [
        ("ready", "queued", -1, None, False, "queued", 0),
        ("delayed", "queued", 60, None, False, "queued", 0),
        ("expired", "running", -1, -1, False, "running", 1),
        ("cleanup", "queued", -1, None, False, "queued", 9),
        ("active", "running", -1, 60, False, "running", 1),
        ("cancelled-active", "running", -1, 60, True, "cancelled", 1),
        ("cancelled-ready", "queued", -1, None, True, "queued", 0),
        ("terminal", "succeeded", -1, None, False, "succeeded", 1),
    ]
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        for name, status, available, lease, cancelled, item_status, attempts in values:
            await connection.execute(batches.insert().values(id=name, cancelled=cancelled))
            await connection.execute(
                jobs.insert().values(
                    id=name,
                    kind="knowledge.bulk.intake" if kind == "bulk_intake" else "knowledge.bulk.query",
                    status=status,
                    available_at=now + timedelta(seconds=available),
                    lease_until=now + timedelta(seconds=lease) if lease else None,
                    attempts=attempts,
                    max_attempts=3,
                    created_at=now - timedelta(seconds=10),
                )
            )
            await connection.execute(items.insert().values(job_id=name, batch_id=name, status=item_status))
        spec = next(spec for spec in bulk_queue_specifications(now) if spec.name == kind)
        row = (
            (
                await connection.execute(
                    queue_statement(spec.table, spec.ready, spec.active, spec.retry, spec.created, limit=100)
                )
            )
            .mappings()
            .one()
        )
        assert row["ready"] == 3 and row["active"] == 2 and row["retry"] == 2
    await engine.dispose()
