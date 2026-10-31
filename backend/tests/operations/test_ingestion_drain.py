# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

import sqlalchemy as sa
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry

from koinon.workers.ingestion import pending_statement


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
