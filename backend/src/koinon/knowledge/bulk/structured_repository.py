# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product operation receipts on the existing native Structured datasource."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from flyquery.config import FlyquerySettings
from flyquery.models.entities.dataset import Dataset
from flyquery.models.entities.file import File
from flyquery.models.entities.schema import SchemaSnapshot
from flyquery.models.entities.table import Table
from pydantic import ValidationError
from pyfly.container import Provider, repository
from pyfly.data.relational.datasource_registry import DataSource
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.knowledge.bulk.entities import now
from koinon.knowledge.bulk.structured_dtos import (
    PreparedStructuredTable,
    StructuredCommitReceipt,
    StructuredOperationIdentity,
    StructuredOperationState,
    StructuredTablePlan,
)
from koinon.knowledge.bulk.structured_entities import StructuredBulkOperation
from koinon.knowledge.lineage.entities import SnapshotLineageRow, SourceArtifactRow, TransformRunRow


def native_conflict() -> ConflictException:
    return ConflictException(
        "Native bulk operation differs from its immutable reservation", code="BULK_NATIVE_RECEIPT_CONFLICT"
    )


def operation_identity(row: StructuredBulkOperation) -> StructuredOperationIdentity:
    values = {
        field: getattr(row, field)
        for field in StructuredOperationIdentity.model_fields
        if field != "operation_id"
    }
    try:
        return StructuredOperationIdentity(operation_id=row.id, **values)
    except ValidationError:
        raise native_conflict() from None


def state(row: StructuredBulkOperation) -> StructuredOperationState:
    try:
        return StructuredOperationState.model_validate(
            {
                "identity": operation_identity(row),
                "status": row.status,
                "plan": row.plan_json or [],
                "prepared": row.prepared_json or [],
                "receipt": row.receipt_json,
            }
        )
    except ValidationError:
        raise native_conflict() from None


class StructuredBulkUnit:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def _row(
        self, identity: StructuredOperationIdentity, *, lock: bool = False
    ) -> StructuredBulkOperation | None:
        statement = select(StructuredBulkOperation).where(
            StructuredBulkOperation.id == identity.operation_id,
            StructuredBulkOperation.tenant_id == identity.tenant_id,
            StructuredBulkOperation.workspace_id == identity.workspace_id,
            StructuredBulkOperation.dataset_id == identity.dataset_id,
            StructuredBulkOperation.file_id == identity.file_id,
            StructuredBulkOperation.actor == identity.actor,
        )
        if lock:
            statement = statement.with_for_update()
        row = await self._session.scalar(statement.execution_options(populate_existing=True))
        if row is not None and operation_identity(row) != identity:
            raise native_conflict()
        return row

    async def get(self, identity: StructuredOperationIdentity) -> StructuredOperationState | None:
        row = await self._row(identity)
        return state(row) if row is not None else None

    async def admit(self, identity: StructuredOperationIdentity) -> StructuredOperationState:
        previous = await self._row(identity, lock=True)
        if previous is not None:
            return state(previous)
        clock = now()
        self._session.add(
            Dataset(
                id=identity.dataset_id,
                tenant_id=identity.tenant_id,
                workspace_id=identity.workspace_id,
                name="bulk-" + str(identity.operation_id),
                description=None,
                drift_policy="AUTO",
                default_locale=None,
                ingest_policy_json={},
                status="ACTIVE",
                created_at=clock,
                updated_at=clock,
                metadata_json={
                    "catalog_source_id": identity.catalog_source_id,
                    "bulk_operation_id": str(identity.operation_id),
                },
            )
        )
        await self._session.flush()
        values = identity.model_dump(mode="python")
        values["id"] = values.pop("operation_id")
        row = StructuredBulkOperation(**values, status="admitted", created_at=clock)
        self._session.add(row)
        await self._session.flush()
        return state(row)

    async def plan(
        self, identity: StructuredOperationIdentity, tables: tuple[StructuredTablePlan, ...]
    ) -> StructuredOperationState:
        if (
            not 1 <= len(tables) <= 16
            or tuple(t.ordinal for t in tables) != tuple(range(len(tables)))
            or len({t.table_id for t in tables}) != len(tables)
            or len({t.snapshot_id for t in tables}) != len(tables)
            or len({t.name for t in tables}) != len(tables)
            or any(t.catalog_table_id is None for t in tables)
            or len({t.catalog_table_id for t in tables}) != len(tables)
        ):
            raise native_conflict()
        row = await self._row(identity, lock=True)
        if row is None:
            raise native_conflict()
        payload = [table.model_dump(mode="json") for table in tables]
        if row.plan_json is not None and row.plan_json != payload:
            raise native_conflict()
        if row.plan_json is None:
            if row.status != "admitted":
                raise native_conflict()
            row.plan_json = payload
            await self._session.flush()
        return state(row)

    async def _file(self, identity: StructuredOperationIdentity, *, lock: bool = False) -> File:
        dataset_query = select(Dataset).where(
            Dataset.id == identity.dataset_id,
            Dataset.tenant_id == identity.tenant_id,
            Dataset.workspace_id == identity.workspace_id,
        )
        file_query = select(File).where(
            File.id == identity.file_id,
            File.tenant_id == identity.tenant_id,
            File.workspace_id == identity.workspace_id,
            File.dataset_id == identity.dataset_id,
        )
        if lock:
            dataset_query = dataset_query.with_for_update()
            file_query = file_query.with_for_update()
        dataset = await self._session.scalar(dataset_query.execution_options(populate_existing=True))
        if (
            dataset is None
            or dataset.status != "ACTIVE"
            or dataset.metadata_json.get("bulk_operation_id") != str(identity.operation_id)
            or dataset.metadata_json.get("catalog_source_id") != identity.catalog_source_id
        ):
            raise native_conflict()
        row = await self._session.scalar(file_query.execution_options(populate_existing=True))
        if (
            row is None
            or row.original_filename != identity.filename
            or row.size_bytes != identity.size_bytes
            or row.content_hash_sha256 != identity.sha256
            or row.uploaded_by != identity.actor
            or row.status not in {"RECEIVED", "PARSED"}
        ):
            raise native_conflict()
        artifact = await self._session.scalar(
            select(SourceArtifactRow).where(
                SourceArtifactRow.id == identity.file_id,
                SourceArtifactRow.tenant_id == identity.tenant_id,
                SourceArtifactRow.workspace_id == identity.workspace_id,
                SourceArtifactRow.dataset_id == identity.dataset_id,
            )
        )
        if (
            artifact is None
            or artifact.actor != identity.actor
            or artifact.sha256 != identity.sha256
            or artifact.byte_size != identity.size_bytes
            or artifact.original_filename != identity.filename
        ):
            raise native_conflict()
        return row

    async def _table(
        self,
        identity: StructuredOperationIdentity,
        prepared: PreparedStructuredTable,
        *,
        ready: bool,
        lock: bool = False,
    ) -> None:
        table_query = select(Table).where(
            Table.id == prepared.table_id,
            Table.tenant_id == identity.tenant_id,
            Table.workspace_id == identity.workspace_id,
            Table.dataset_id == identity.dataset_id,
        )
        snapshot_query = select(SchemaSnapshot).where(
            SchemaSnapshot.id == prepared.snapshot_id,
            SchemaSnapshot.tenant_id == identity.tenant_id,
            SchemaSnapshot.workspace_id == identity.workspace_id,
            SchemaSnapshot.dataset_id == identity.dataset_id,
            SchemaSnapshot.table_id == prepared.table_id,
        )
        if lock:
            table_query = table_query.with_for_update()
            snapshot_query = snapshot_query.with_for_update()
        table = await self._session.scalar(table_query.execution_options(populate_existing=True))
        snapshot = await self._session.scalar(snapshot_query.execution_options(populate_existing=True))
        if (
            table is None
            or snapshot is None
            or table.source_file_id != identity.file_id
            or table.name != prepared.name
            or not table.is_active
            or table.archived_at is not None
            or table.current_snapshot_id != (prepared.snapshot_id if ready else None)
            or snapshot.status != ("READY" if ready else "PARTIAL")
            or snapshot.parquet_object_key != prepared.parquet_key
            or snapshot.parquet_byte_size != prepared.parquet_byte_size
            or snapshot.n_columns != prepared.n_columns
            or snapshot.n_rows_actual != prepared.n_rows_actual
            or snapshot.snapshot_hash != prepared.schema_sha256
        ):
            raise native_conflict()
        lineage = await self._session.scalar(
            select(SnapshotLineageRow).where(
                SnapshotLineageRow.snapshot_id == prepared.snapshot_id,
                SnapshotLineageRow.table_id == prepared.table_id,
                SnapshotLineageRow.tenant_id == identity.tenant_id,
                SnapshotLineageRow.workspace_id == identity.workspace_id,
                SnapshotLineageRow.dataset_id == identity.dataset_id,
            )
        )
        if (
            lineage is None
            or lineage.run_id != prepared.lineage_run_id
            or lineage.parquet_sha256 != prepared.parquet_sha256
            or lineage.parquet_byte_size != prepared.parquet_byte_size
            or lineage.schema_sha256 != prepared.schema_sha256
            or lineage.row_count != prepared.n_rows_actual
        ):
            raise native_conflict()
        run = await self._session.scalar(
            select(TransformRunRow).where(
                TransformRunRow.id == prepared.lineage_run_id,
                TransformRunRow.tenant_id == identity.tenant_id,
                TransformRunRow.workspace_id == identity.workspace_id,
                TransformRunRow.dataset_id == identity.dataset_id,
            )
        )
        if (
            run is None
            or run.actor != identity.actor
            or run.artifact_id != identity.file_id
            or run.operation != "upload"
            or run.predecessor_snapshot_id is not None
        ):
            raise native_conflict()

    async def prepared(
        self, identity: StructuredOperationIdentity, tables: tuple[PreparedStructuredTable, ...]
    ) -> StructuredOperationState:
        row = await self._row(identity, lock=True)
        if row is None or row.plan_json is None or not 1 <= len(tables) <= 16:
            raise native_conflict()
        payload = [table.model_dump(mode="json") for table in tables]
        expected = [
            StructuredTablePlan.model_validate(
                {field: getattr(table, field) for field in StructuredTablePlan.model_fields}
            ).model_dump(mode="json")
            for table in tables
        ]
        if expected != row.plan_json:
            raise native_conflict()
        if row.prepared_json is not None:
            if row.prepared_json != payload:
                raise native_conflict()
            return state(row)
        if row.status != "admitted":
            raise native_conflict()
        await self._file(identity)
        for table in tables:
            await self._table(identity, table, ready=False)
        row.prepared_json = payload
        row.status = "prepared"
        await self._session.flush()
        return state(row)

    async def publication(self, identity: StructuredOperationIdentity) -> StructuredOperationState:
        row = await self._row(identity, lock=True)
        if row is None:
            raise native_conflict()
        if row.status == "committed":
            return state(row)
        if row.status != "prepared" or not row.prepared_json:
            raise native_conflict()
        tables = state(row).prepared
        await self._file(identity, lock=True)
        for table in sorted(tables, key=lambda value: str(value.table_id)):
            await self._table(identity, table, ready=False, lock=True)
        return state(row)

    async def commit(self, identity: StructuredOperationIdentity) -> StructuredOperationState:
        row = await self._row(identity, lock=True)
        if row is None:
            raise native_conflict()
        if row.status == "committed":
            return state(row)
        if row.status != "prepared" or not row.prepared_json:
            raise native_conflict()
        tables = state(row).prepared
        file = await self._file(identity)
        for table in tables:
            await self._table(identity, table, ready=True)
        receipt = StructuredCommitReceipt(
            file_id=identity.file_id,
            dataset_id=identity.dataset_id,
            sha256=identity.sha256,
            size_bytes=identity.size_bytes,
            object_key=file.object_store_key,
            tables=tables,
        )
        row.receipt_json = receipt.model_dump(mode="json")
        row.status = "committed"
        file.status = "PARSED"
        await self._session.flush()
        return state(row)


@repository(name="knowledge.bulk.structured_repository")
class StructuredBulkRepository:
    def __init__(self, settings: Provider[FlyquerySettings | None]):
        self.settings = settings

    def configuration(self) -> FlyquerySettings:
        settings = self.settings.get()
        if settings is None:
            raise ServiceUnavailableException(
                "Native structured resources are unavailable", code="BULK_NATIVE_REQUIRED"
            )
        return settings

    def native(self) -> DataSource:
        return self.configuration().native_datasource()

    def _native(self) -> DataSource:
        return self.native()

    @asynccontextmanager
    async def read(self) -> AsyncIterator[StructuredBulkUnit]:
        async with infrastructure_unit(self._native(), read_only=True) as session:
            yield StructuredBulkUnit(session)

    @asynccontextmanager
    async def write(self) -> AsyncIterator[StructuredBulkUnit]:
        async with infrastructure_unit(self._native()) as session:
            yield StructuredBulkUnit(session)
