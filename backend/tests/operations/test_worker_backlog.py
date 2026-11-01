# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from koinon.workers.observations import measure_queue


async def test_counts_include_active_work_cap_rows_and_return_no_private_identifiers(tmp_path):
    registry = DataSourceRegistry.for_config(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'counts.db'}",
                            "ddl-auto": "none",
                        }
                    }
                }
            }
        )
    )
    metadata = sa.MetaData()
    table = sa.Table(
        "jobs",
        metadata,
        sa.Column("private_id", sa.String),
        sa.Column("status", sa.String),
        sa.Column("attempts", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    async with registry.primary.engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(
            table.insert(),
            [
                {
                    "private_id": "private-one",
                    "status": "ready",
                    "attempts": 0,
                    "created_at": now - timedelta(seconds=60),
                },
                {
                    "private_id": "private-two",
                    "status": "active",
                    "attempts": 1,
                    "created_at": now - timedelta(seconds=30),
                },
                {
                    "private_id": "private-three",
                    "status": "ready",
                    "attempts": 1,
                    "created_at": now - timedelta(seconds=10),
                },
                {
                    "private_id": "private-done",
                    "status": "done",
                    "attempts": 1,
                    "created_at": now - timedelta(seconds=90),
                },
            ],
        )
    try:
        view = await measure_queue(
            registry.primary,
            "conversation",
            table,
            table.c.status == "ready",
            table.c.status == "active",
            table.c.attempts > 0,
            table.c.created_at,
            capacity=2,
            limit=10,
        )
        assert view.ready == 2 and view.active == 1 and view.retry == 1 and view.demand == 3
        assert 59 <= view.oldest_ready_age_seconds <= 62
        assert view.capacity == 2 and not view.capped and view.available
        assert "private-" not in str(view)
        capped = await measure_queue(
            registry.primary,
            "conversation",
            table,
            table.c.status == "ready",
            table.c.status == "active",
            table.c.attempts > 0,
            table.c.created_at,
            capacity=2,
            limit=2,
        )
        assert capped.capped and capped.demand == 2
    finally:
        await registry.close()


async def test_capacity_reports_the_shared_process_limit_without_summing_queue_limits():
    from types import SimpleNamespace

    from koinon.operations.settings import OperationalSettings
    from koinon.workers.admission import WorkAdmissionSettings
    from koinon.workers.observations import WorkerBacklog

    view = await WorkerBacklog(
        SimpleNamespace(names=lambda: []),
        OperationalSettings(worker_concurrency=8),
        SimpleNamespace(contains_type=lambda kind: False),
        WorkAdmissionSettings(worker_capacity=1),
    ).snapshot()
    assert view.process_capacity == 1
    assert len(view.queues) == 10
    assert all(row.capacity == 1 and not row.available for row in view.queues)
