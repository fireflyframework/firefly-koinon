# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from importlib import import_module
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit


@pytest.mark.parametrize("domain", ["canon", "structured"])
@pytest.mark.parametrize("phase", ["stale begin", "revoked before commit"])
async def test_native_stage_transaction_cannot_publish_from_stale_or_revoked_execution(
    tmp_path, domain, phase
):
    package = "flycanon" if domain == "canon" else "flyquery"
    lease_module = import_module(
        package + (".core.services.sources" if domain == "canon" else ".core.services.ingestion") + ".lease"
    )
    registry = DataSourceRegistry.for_config(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'stage.db'}",
                            "ddl-auto": "none",
                        }
                    }
                }
            }
        )
    )
    metadata = sa.MetaData()
    native = domain == "structured"
    jobs = sa.Table(
        "flyquery_ingest_jobs" if native else "canon_ingest_jobs",
        metadata,
        sa.Column("id", sa.Uuid if native else sa.String),
        sa.Column("tenant_id", sa.String),
        sa.Column("workspace_id", sa.Uuid if native else sa.String),
        sa.Column("attempts", sa.Integer),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String),
    )
    published = sa.Table("published", metadata, sa.Column("body", sa.String))
    identifier, workspace = (uuid4(), uuid4()) if native else ("job", "workspace")
    started = datetime.now(UTC)
    async with registry.primary.engine.begin() as connection:
        await connection.run_sync(metadata.create_all)
        await connection.execute(
            jobs.insert().values(
                id=identifier,
                tenant_id="north",
                workspace_id=workspace,
                attempts=1,
                started_at=started,
                status="RUNNING" if native else "running",
            )
        )
    customizer = import_module(package + ".data").TenantGucCustomizer("primary")
    registry.add_customizer(customizer)
    lease = lease_module.IngestLease(
        identifier, "north", workspace, 1, started, started + timedelta(seconds=60)
    )
    revoked = False

    async def authorize():
        if revoked:
            raise PermissionError("Current authority revoked")

    try:
        if phase == "stale begin":
            async with registry.primary.engine.begin() as connection:
                await connection.execute(
                    jobs.update().values(attempts=2, started_at=started + timedelta(seconds=1))
                )
        with (
            lease_module.bind_ingest_lease(lease, authorize),
            pytest.raises(lease_module.IngestLeaseLost if phase == "stale begin" else PermissionError),
        ):
            async with infrastructure_unit(registry.primary) as session:
                await session.execute(published.insert().values(body="must not publish"))
                revoked = True
        assert lease_module.current_ingest_lease() is None
        async with registry.primary.engine.connect() as connection:
            assert await connection.scalar(sa.select(sa.func.count()).select_from(published)) == 0
        assert registry.primary.engine.pool.checkedout() == 0
    finally:
        await registry.close()
