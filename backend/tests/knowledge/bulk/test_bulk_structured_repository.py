# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.kernel import ConflictException
from sqlalchemy import JSON, Column, MetaData, func
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
                        server_default=func.current_timestamp()
                        if c.name in {"created_at", "updated_at"} and c.server_default is not None
                        else None,
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


async def test_source_operation_freezes_descriptor_only_after_its_exact_member_plan(operations):
    from koinon.knowledge.bulk.ports import SourcePublicationBinding

    owned = identity()
    binding = SourcePublicationBinding("attempt", "b" * 64)
    async with operations.write() as unit:
        await unit.admit(owned, source_attempt_id=binding.attempt_id)
    with pytest.raises(ConflictException):
        async with operations.write() as unit:
            await unit.bind_publication(owned, binding)
    plan = (
        StructuredTablePlan(
            ordinal=0,
            table_id=uuid4(),
            snapshot_id=uuid4(),
            name="facts",
            catalog_table_id="catalog-table",
        ),
    )
    async with operations.write() as unit:
        await unit.plan(owned, plan)
        frozen = await unit.bind_publication(owned, binding)
        assert frozen.source_attempt_id == binding.attempt_id
        assert frozen.source_publication_sha256 == binding.descriptor_sha256
    async with operations.write() as unit:
        assert await unit.bind_publication(owned, binding) == frozen
    for changed in (
        SourcePublicationBinding("different", binding.descriptor_sha256),
        SourcePublicationBinding(binding.attempt_id, "c" * 64),
    ):
        with pytest.raises(ConflictException):
            async with operations.write() as unit:
                await unit.bind_publication(owned, changed)
    with pytest.raises(ConflictException):
        async with operations.write() as unit:
            await unit.admit(owned)


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


async def seed_prepared(operations, owned, plans, *, predecessors=None, materialize=True):
    from datetime import UTC, datetime

    from flyquery.core.services.ingestion.stages.reconcile import DeferredReconcileChanges
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
            if materialize and (not predecessors or plan.table_id not in predecessors):
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
                        is_active=predecessors is None,
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
                    operation="replace" if predecessors and plan.table_id in predecessors else "upload",
                    predecessor_snapshot_id=(predecessors or {}).get(plan.table_id),
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
            qualified_name="replacement." + plan.name if predecessors is not None else None,
            sheet_or_json_path=plan.member_key if predecessors is not None else None,
            reconcile_changes=DeferredReconcileChanges(
                tenant_id=owned.tenant_id,
                workspace_id=owned.workspace_id,
                table_id=plan.table_id,
                previous_snapshot_id=predecessors[plan.table_id],
                next_snapshot_id=plan.snapshot_id,
                removed_object_ids=(),
                changes=(),
            )
            if predecessors and plan.table_id in predecessors
            else None,
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


@pytest.mark.parametrize("changed", [None, "missing_member", "old_head", "foreign_file", "replay", "plan"])
async def test_replacement_admission_preserves_live_dataset_and_requires_exact_whole_file(
    operations, changed
):
    from flyquery.models.entities.dataset import Dataset
    from flyquery.models.entities.table import Table
    from pyfly.data.transaction import infrastructure_unit
    from sqlalchemy import func, select

    from koinon.knowledge.bulk.structured_dtos import DatasetReplacementBaseline

    owned = identity()
    plans = tuple(
        StructuredTablePlan(
            ordinal=i,
            table_id=uuid4(),
            snapshot_id=uuid4(),
            name=f"facts_{i}",
            catalog_table_id=f"catalog-{i}",
            member_key=f'json:["section{i}"]',
        )
        for i in range(2)
    )
    async with operations.write() as unit:
        await unit.admit(owned)
        await unit.plan(owned, plans)
    tables = await seed_prepared(operations, owned, plans)
    async with operations.write() as unit:
        await unit.prepared(owned, tables)
    await publish_in_unit(operations, owned, tables)
    async with operations.write() as unit:
        await unit.commit(owned)
    replacement = identity(
        workspace_id=owned.workspace_id,
        dataset_id=owned.dataset_id,
        catalog_file_version_id="replacement-version",
        sha256="b" * 64,
    )
    baseline = DatasetReplacementBaseline.model_validate(
        {
            "dataset_id": owned.dataset_id,
            "catalog_dataset_id": owned.catalog_dataset_id,
            "source_attempt_id": "previous",
            "imported_version_id": "previous",
            "catalog_file_version_id": owned.catalog_file_version_id,
            "policy_id": "policy",
            "local_revision": "cpv1:" + "c" * 64,
            "source_generation": 1,
            "policy_revision": 1,
            "sha256": owned.sha256,
            "native_file_id": owned.file_id,
            "members": [
                {
                    "member_key": table.member_key,
                    "table_id": table.table_id,
                    "catalog_table_id": table.catalog_table_id,
                    "snapshot_id": table.snapshot_id,
                    "source_file_id": owned.file_id,
                    "local_revision": "cpv1:" + "c" * 64,
                    "sha256": owned.sha256,
                }
                for table in tables
            ],
        }
    )
    original = baseline
    if changed == "missing_member":
        baseline = baseline.model_copy(update={"members": baseline.members[:1]})
    elif changed == "old_head":
        baseline = baseline.model_copy(
            update={
                "members": (
                    baseline.members[0].model_copy(update={"snapshot_id": uuid4()}),
                    baseline.members[1],
                )
            }
        )
    elif changed == "foreign_file":
        replacement = replacement.model_copy(update={"file_id": owned.file_id})
    if changed in {"missing_member", "old_head", "foreign_file"}:
        with pytest.raises(ConflictException):
            async with operations.write() as unit:
                await unit.admit_replacement(
                    replacement,
                    source_attempt_id="replacement",
                    baseline=baseline,
                    baseline_sha256="d" * 64,
                )
    else:
        async with operations.write() as unit:
            admitted = await unit.admit_replacement(
                replacement,
                source_attempt_id="replacement",
                baseline=baseline,
                baseline_sha256="d" * 64,
            )
            assert admitted.operation_kind == "replace" and admitted.baseline == original
        async with operations.write() as unit:
            assert (
                await unit.admit_replacement(
                    replacement,
                    source_attempt_id="replacement",
                    baseline=baseline,
                    baseline_sha256="d" * 64,
                )
                == admitted
            )
        if changed == "replay":
            with pytest.raises(ConflictException):
                async with operations.write() as unit:
                    await unit.admit_replacement(
                        replacement,
                        source_attempt_id="foreign",
                        baseline=baseline,
                        baseline_sha256="d" * 64,
                    )
        if changed == "plan":
            from koinon.knowledge.bulk.structured_replacement import ReplacementMemberPlan

            retained = ReplacementMemberPlan(
                member_key=plans[1].member_key,
                action="retain",
                table_id=plans[1].table_id,
                catalog_table_id=plans[1].catalog_table_id,
                snapshot_id=uuid4(),
                ordinal=0,
                name="retained",
            )
            added = ReplacementMemberPlan(
                member_key='json:["new"]',
                action="add",
                table_id=uuid4(),
                catalog_table_id="new-table",
                snapshot_id=uuid4(),
                ordinal=1,
                name=plans[0].name,
            )
            removed = ReplacementMemberPlan(
                member_key=plans[0].member_key,
                action="remove",
                table_id=plans[0].table_id,
                catalog_table_id=plans[0].catalog_table_id,
                snapshot_id=plans[0].snapshot_id,
            )
            members = (retained, added, removed)
            for invalid in (
                members[:2],
                (retained.model_copy(update={"catalog_table_id": "foreign"}), added, removed),
                (retained, added.model_copy(update={"ordinal": 0}), removed),
                (retained, added.model_copy(update={"table_id": removed.table_id}), removed),
            ):
                with pytest.raises(ConflictException):
                    async with operations.write() as unit:
                        await unit.plan_replacement(replacement, invalid)
            async with operations.write() as unit:
                planned = await unit.plan_replacement(replacement, members)
                assert planned.replacement_plan == members
                assert tuple(member.table_id for member in planned.plan) == (
                    retained.table_id,
                    added.table_id,
                )
            async with operations.write() as unit:
                assert await unit.plan_replacement(replacement, members) == planned
                from koinon.knowledge.bulk.ports import SourcePublicationBinding

                await unit.bind_publication(replacement, SourcePublicationBinding("replacement", "e" * 64))
            prepared = await seed_prepared(
                operations,
                replacement,
                planned.plan,
                predecessors={retained.table_id: original.members[1].snapshot_id},
                materialize=False,
            )
            async with operations.write() as unit:
                for plan in planned.plan:
                    await unit.materialize_table(
                        replacement,
                        plan,
                        SimpleNamespace(
                            table_id=plan.table_id,
                            name=plan.name,
                            qualified_name="replacement." + plan.name,
                            sheet_or_json_path=plan.member_key,
                        ),
                    )
                old = await unit._session.get(Table, retained.table_id)
                assert old.name == plans[1].name and old.current_snapshot_id == plans[1].snapshot_id
                staged = await unit._session.get(Table, added.table_id)
                assert staged.name == plans[0].name and staged.is_active is False
            async with operations.write() as unit:
                accepted = await unit.prepared(replacement, prepared)
                assert accepted.status == "prepared"
            async with operations.write() as unit:
                assert await unit.publication(replacement) == accepted
            async with operations.write() as unit:
                assert await unit.plan_replacement(replacement, members) == accepted
            with pytest.raises(RuntimeError, match="publication cancelled"):
                async with operations.write() as unit:
                    await unit.activate_replacement(replacement)
                    raise RuntimeError("publication cancelled")
            async with operations.write() as unit:
                assert await unit.publication(replacement) == accepted
                await unit.activate_replacement(replacement)
                from flyquery.models.entities.schema import SchemaSnapshot

                for table in prepared:
                    live = await unit._session.get(Table, table.table_id)
                    assert live.name == table.name and live.qualified_name == table.qualified_name
                    assert live.sheet_or_json_path == table.sheet_or_json_path and live.is_active
                    live.current_snapshot_id = table.snapshot_id
                    (await unit._session.get(SchemaSnapshot, table.snapshot_id)).status = "READY"
                await unit._session.flush()
                final = await unit.commit(replacement)
                assert final.status == "committed"
                assert final.receipt.tables == prepared
    async with infrastructure_unit(operations._native()) as session:
        assert await session.scalar(select(func.count()).select_from(Dataset)) == 1
        for plan in plans:
            table = await session.get(Table, plan.table_id)
            if changed == "plan" and plan.table_id == retained.table_id:
                assert (
                    table.current_snapshot_id == retained.snapshot_id
                    and table.source_file_id == replacement.file_id
                )
            else:
                assert table.current_snapshot_id == plan.snapshot_id and table.source_file_id == owned.file_id
                if changed == "plan":
                    assert not table.is_active and table.archived_at is not None and table.name == plan.name


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


async def test_prepared_reconcile_changes_are_retained_but_cannot_target_another_member(operations):
    from flyquery.core.services.ingestion.stages.reconcile import DeferredReconcileChanges
    from pydantic import ValidationError

    from koinon.knowledge.bulk.structured_dtos import PreparedStructuredTable

    owned = identity()
    plans = (
        StructuredTablePlan(
            ordinal=0, table_id=uuid4(), snapshot_id=uuid4(), name="facts", catalog_table_id="catalog-table"
        ),
    )
    async with operations.write() as unit:
        await unit.admit(owned)
        await unit.plan(owned, plans)
    tables = await seed_prepared(operations, owned, plans)
    change = DeferredReconcileChanges(
        tenant_id=owned.tenant_id,
        workspace_id=owned.workspace_id,
        table_id=plans[0].table_id,
        previous_snapshot_id=uuid4(),
        next_snapshot_id=plans[0].snapshot_id,
        removed_object_ids=(),
        changes=(),
    )
    retained = PreparedStructuredTable.model_validate({**tables[0].model_dump(), "reconcile_changes": change})
    assert (
        retained.model_dump(mode="json", by_alias=True)["reconcile_changes"]["schema"]
        == "koinon.structured-reconcile-changes.v1"
    )
    with pytest.raises(ValidationError):
        PreparedStructuredTable.model_validate({**retained.model_dump(), "table_id": uuid4()})
    with pytest.raises(ConflictException):
        async with operations.write() as unit:
            await unit.prepared(owned, (retained,))


async def test_dataset_receipt_inspection_does_not_load_filename_plan_or_table_names(operations):
    from unittest.mock import AsyncMock

    from sqlalchemy import event

    from koinon.knowledge.bulk.dataset_native import DatasetBulkNative

    owned = identity()
    plans = (
        StructuredTablePlan(
            ordinal=0,
            table_id=uuid4(),
            snapshot_id=uuid4(),
            name="protected-table-name",
            catalog_table_id="table",
        ),
    )
    async with operations.write() as unit:
        await unit.admit(owned)
        await unit.plan(owned, plans)
    tables = await seed_prepared(operations, owned, plans)
    async with operations.write() as unit:
        await unit.prepared(owned, tables)
        await unit.publication(owned)
        await publish_in_unit(operations, owned, tables)
        await unit.commit(owned)
    queries = []

    def capture(connection, cursor, statement, parameters, context, many):
        queries.append(statement)

    engine = operations._native().engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        service = DatasetBulkNative(operations, None, None, None, None)
        service.identity = AsyncMock(return_value=owned)
        observed = await service.inspect(SimpleNamespace(tenant_id=owned.tenant_id, subject=owned.actor))
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert observed.status == "committed" and observed.receipt.tables[0].catalog_table_id == "table"
    assert "protected-table-name" not in repr(observed)
    for query in queries:
        selection = query.upper().split("FROM")[0]
        assert (
            "FILENAME" not in selection and "PLAN_JSON" not in selection and "PREPARED_JSON" not in selection
        )
