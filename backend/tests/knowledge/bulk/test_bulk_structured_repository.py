# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.kernel import ConflictException
from sqlalchemy import JSON, Column, MetaData
from sqlalchemy import Table as SQLTable
from sqlalchemy.dialects.postgresql import JSONB

from koinon.knowledge.bulk.structured_dtos import StructuredOperationIdentity, StructuredTablePlan


@pytest.fixture
async def operations(tmp_path):
    from flyquery.models.entities.dataset import Dataset
    from flyquery.models.entities.file import File
    from flyquery.models.entities.schema import SchemaSnapshot
    from flyquery.models.entities.table import Table

    from koinon.knowledge.bulk.structured_entities import StructuredBulkOperation
    from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository
    from koinon.knowledge.lineage.entities import SnapshotLineageRow, SourceArtifactRow, TransformRunRow

    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'primary.db'}",
                            "datasources": {
                                "structured": {
                                    "url": f"sqlite+aiosqlite:///{tmp_path / 'structured.db'}",
                                    "ddl-auto": "none",
                                }
                            },
                        }
                    }
                }
            }
        )
    )
    context.register_bean(StructuredBulkRepository)
    await context.start()
    try:
        native = context.get_bean(DataSourceRegistry).get("structured")
        metadata = MetaData()
        for entity in [Dataset, File, Table, SchemaSnapshot]:
            SQLTable(
                entity.__tablename__,
                metadata,
                *[
                    Column(
                        c.name,
                        JSON() if isinstance(c.type, JSONB) else c.type,
                        primary_key=c.primary_key,
                        nullable=c.nullable,
                    )
                    for c in entity.__table__.columns
                ],
            )
        async with native.engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            await connection.run_sync(StructuredBulkOperation.__table__.create)
            for entity in [SourceArtifactRow, TransformRunRow, SnapshotLineageRow]:
                await connection.run_sync(entity.__table__.create)
        repository = context.get_bean(StructuredBulkRepository)
        repository.settings = SimpleNamespace(get=lambda: SimpleNamespace(native_datasource=lambda: native))
        yield repository
    finally:
        await context.stop()


def identity(**changes):
    value = {
        "operation_id": uuid4(),
        "tenant_id": "north",
        "workspace_id": uuid4(),
        "dataset_id": uuid4(),
        "file_id": uuid4(),
        "actor": "issuer|owner",
        "catalog_source_id": "source",
        "catalog_dataset_id": "dataset",
        "catalog_file_version_id": "version",
        "filename": "facts.csv",
        "sha256": "a" * 64,
        "size_bytes": 8,
    }
    return StructuredOperationIdentity(**{**value, **changes})


async def test_native_admission_and_plan_survive_new_units_and_reject_cross_scope_or_changed_identity(
    operations,
):
    owned = identity()
    async with operations.write() as unit:
        admitted = await unit.admit(owned)
    assert admitted.status == "admitted"
    plan = (
        StructuredTablePlan(
            ordinal=0, table_id=uuid4(), snapshot_id=uuid4(), name="facts", catalog_table_id="catalog-table"
        ),
    )
    async with operations.write() as unit:
        await unit.plan(owned, plan)
    async with operations.read() as unit:
        stored = await unit.get(owned)
        assert stored.identity == owned and stored.plan == plan
        assert await unit.get(owned.model_copy(update={"tenant_id": "south"})) is None
    async with operations.write() as unit:
        assert (await unit.admit(owned)).plan == plan
    with pytest.raises(ConflictException):
        async with operations.write() as unit:
            await unit.admit(owned.model_copy(update={"sha256": "b" * 64}))
    with pytest.raises(ConflictException):
        async with operations.write() as unit:
            await unit.plan(owned, (plan[0].model_copy(update={"table_id": uuid4()}),))


async def seed_prepared(operations, owned, plans):
    from datetime import UTC, datetime

    from flyquery.models.entities.file import File
    from flyquery.models.entities.schema import SchemaSnapshot
    from flyquery.models.entities.table import Table
    from pyfly.data.transaction import infrastructure_unit

    from koinon.knowledge.bulk.structured_dtos import PreparedStructuredTable
    from koinon.knowledge.lineage.entities import SnapshotLineageRow, SourceArtifactRow, TransformRunRow

    clock = datetime.now(UTC)
    scoped = dict(
        tenant_id=owned.tenant_id,
        workspace_id=owned.workspace_id,
        dataset_id=owned.dataset_id,
        actor=owned.actor,
        recorded_at=clock,
    )
    runs = {plan.table_id: uuid4() for plan in plans}
    async with infrastructure_unit(operations._native()) as session:
        session.add(
            File(
                id=owned.file_id,
                tenant_id=owned.tenant_id,
                workspace_id=owned.workspace_id,
                dataset_id=owned.dataset_id,
                original_filename=owned.filename,
                file_format="csv",
                compression="none",
                size_bytes=owned.size_bytes,
                content_hash_sha256=owned.sha256,
                object_store_key="raw/owned",
                uploaded_by=owned.actor,
                uploaded_at=clock,
                table_extraction_rules_json={},
                status="RECEIVED",
            )
        )
        session.add(
            SourceArtifactRow(
                id=owned.file_id,
                original_filename=owned.filename,
                sha256=owned.sha256,
                byte_size=owned.size_bytes,
                file_format="csv",
                compression="none",
                **scoped,
            )
        )
        for plan in plans:
            session.add(
                Table(
                    id=plan.table_id,
                    tenant_id=owned.tenant_id,
                    workspace_id=owned.workspace_id,
                    dataset_id=owned.dataset_id,
                    source_file_id=owned.file_id,
                    name=plan.name,
                    qualified_name=plan.name,
                    kind="UPLOADED",
                    is_active=True,
                    created_at=clock,
                    updated_at=clock,
                )
            )
            session.add(
                SchemaSnapshot(
                    id=plan.snapshot_id,
                    tenant_id=owned.tenant_id,
                    workspace_id=owned.workspace_id,
                    dataset_id=owned.dataset_id,
                    table_id=plan.table_id,
                    taken_at=clock,
                    snapshot_hash="c" * 64,
                    n_columns=1,
                    n_rows_actual=1,
                    n_rows_estimate=1,
                    parquet_object_key="parquet/" + str(plan.table_id),
                    parquet_byte_size=7,
                    status="PARTIAL",
                    triggered_by="USER",
                    created_by=owned.actor,
                )
            )
            session.add(
                TransformRunRow(
                    id=runs[plan.table_id],
                    artifact_id=owned.file_id,
                    operation="upload",
                    table_label=plan.name,
                    implementation="inert.parser",
                    parameters={},
                    **scoped,
                )
            )
            session.add(
                SnapshotLineageRow(
                    snapshot_id=plan.snapshot_id,
                    run_id=runs[plan.table_id],
                    table_id=plan.table_id,
                    parquet_sha256="b" * 64,
                    parquet_byte_size=7,
                    schema_sha256="c" * 64,
                    row_count=1,
                    **scoped,
                )
            )
        await session.flush()
    return tuple(
        PreparedStructuredTable(
            **plan.model_dump(),
            lineage_run_id=runs[plan.table_id],
            n_columns=1,
            n_rows_actual=1,
            parquet_key="parquet/" + str(plan.table_id),
            parquet_sha256="b" * 64,
            parquet_byte_size=7,
            schema_sha256="c" * 64,
        )
        for plan in plans
    )


async def publish_in_unit(operations, owned, tables):
    from flyquery.models.entities.schema import SchemaSnapshot
    from flyquery.models.entities.table import Table
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import update

    async with infrastructure_unit(operations._native().sessionmaker) as session:
        for table in tables:
            await session.execute(
                update(Table).where(Table.id == table.table_id).values(current_snapshot_id=table.snapshot_id)
            )
            await session.execute(
                update(SchemaSnapshot).where(SchemaSnapshot.id == table.snapshot_id).values(status="READY")
            )
        await session.flush()


async def test_all_required_tables_and_native_commit_are_atomic_and_cancelled_commit_rolls_back(operations):
    import asyncio

    owned = identity()
    plans = tuple(
        StructuredTablePlan(
            ordinal=i,
            table_id=uuid4(),
            snapshot_id=uuid4(),
            name=f"table_{i}",
            catalog_table_id=f"catalog-table-{i}",
        )
        for i in range(2)
    )
    async with operations.write() as unit:
        await unit.admit(owned)
        await unit.plan(owned, plans)
    tables = await seed_prepared(operations, owned, plans)
    with pytest.raises(ConflictException):
        async with operations.write() as unit:
            await unit.prepared(owned, tables[:1])
    async with operations.write() as unit:
        assert (await unit.prepared(owned, tables)).status == "prepared"
    with pytest.raises(ConflictException):
        async with operations.write() as unit:
            await unit.commit(owned)
    with pytest.raises(asyncio.CancelledError):
        async with operations.write() as unit:
            await unit.publication(owned)
            await publish_in_unit(operations, owned, tables)
            assert (await unit.commit(owned)).status == "committed"
            raise asyncio.CancelledError()
    async with operations.read() as unit:
        assert (await unit.get(owned)).status == "prepared"
    async with operations.write() as unit:
        await unit.publication(owned)
        await publish_in_unit(operations, owned, tables)
        committed = await unit.commit(owned)
        assert committed.status == "committed" and committed.receipt.tables == tables
    async with operations.read() as unit:
        assert (await unit.get(owned)).receipt == committed.receipt
