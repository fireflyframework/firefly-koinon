# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Named native units bind query/result persistence to one immutable operation receipt."""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from flyquery.models.entities.dataset import Dataset
from flyquery.models.entities.queries import Query
from flyquery.models.entities.schema import SchemaSnapshot
from flyquery.models.entities.table import Table
from pydantic import ValidationError
from pyfly.container import repository
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, PayloadTooLargeException
from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository
from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
from koinon.knowledge.bulk_queries.native_entities import NativeQueryOperation
from koinon.knowledge.bulk_queries.native_values import (
    QueryOperationIdentity,
    QueryOperationReceipt,
    QuerySnapshotReference,
)


def conflict() -> ConflictException:
    return ConflictException(
        "Native query receipt differs from its admitted operation", code="BULK_QUERY_RECEIPT_CONFLICT"
    )


def identity_of(row: NativeQueryOperation) -> QueryOperationIdentity:
    try:
        return QueryOperationIdentity(
            operation_id=row.id,
            **{
                name: getattr(row, name)
                for name in QueryOperationIdentity.model_fields
                if name != "operation_id"
            },
        )
    except (ValueError, TypeError):
        raise conflict() from None


def receipt_of(row: NativeQueryOperation) -> QueryOperationReceipt | None:
    if row.status == "admitted":
        if row.receipt_json is not None or row.query_id is not None:
            raise conflict()
        return None
    try:
        receipt = QueryOperationReceipt.model_validate(row.receipt_json)
    except ValidationError:
        raise conflict() from None
    if (
        row.status != "committed"
        or receipt.identity != identity_of(row)
        or receipt.result.query_id != row.query_id
    ):
        raise conflict()
    return receipt


class NativeQueryUnit:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def row(
        self, identity: QueryOperationIdentity, *, lock: bool = False
    ) -> NativeQueryOperation | None:
        statement = select(NativeQueryOperation).where(
            NativeQueryOperation.id == identity.operation_id,
            NativeQueryOperation.tenant_id == identity.tenant_id,
            NativeQueryOperation.subject == identity.subject,
            NativeQueryOperation.workspace_id == identity.workspace_id,
            NativeQueryOperation.dataset_id == identity.dataset_id,
        )
        if lock:
            statement = statement.with_for_update()
        row = await self.session.scalar(statement.execution_options(populate_existing=True))
        if row is not None and identity_of(row) != identity:
            raise conflict()
        return row

    async def admit(self, identity: QueryOperationIdentity) -> None:
        if await self.row(identity, lock=True) is not None:
            raise conflict()
        dataset = await self.session.scalar(
            select(Dataset).where(
                Dataset.id == identity.dataset_id,
                Dataset.workspace_id == identity.workspace_id,
                Dataset.tenant_id == identity.tenant_id,
                Dataset.status == "ACTIVE",
            )
        )
        if dataset is None:
            raise conflict()
        self.session.add(
            NativeQueryOperation(
                id=identity.operation_id, **identity.model_dump(exclude={"operation_id"}), status="admitted"
            )
        )
        await self.session.flush()

    async def snapshots(
        self, identity: QueryOperationIdentity, value: BatchQueryOutcome
    ) -> tuple[QuerySnapshotReference, ...]:
        references = []
        for name, pin in sorted(value.snapshot_pins.items()):
            try:
                snapshot_id = UUID(pin)
            except ValueError:
                raise conflict() from None
            pair = (
                await self.session.execute(
                    select(Table, SchemaSnapshot)
                    .join(SchemaSnapshot, SchemaSnapshot.table_id == Table.id)
                    .where(
                        Table.tenant_id == identity.tenant_id,
                        Table.workspace_id == identity.workspace_id,
                        Table.dataset_id == identity.dataset_id,
                        Table.qualified_name == name,
                        Table.is_active.is_(True),
                        Table.archived_at.is_(None),
                        SchemaSnapshot.id == snapshot_id,
                        SchemaSnapshot.tenant_id == identity.tenant_id,
                        SchemaSnapshot.workspace_id == identity.workspace_id,
                        SchemaSnapshot.dataset_id == identity.dataset_id,
                        SchemaSnapshot.status == "READY",
                    )
                    .with_for_update(read=True)
                )
            ).one_or_none()
            if pair is None:
                raise conflict()
            table, snapshot = pair
            references.append(
                QuerySnapshotReference(table_id=table.id, snapshot_id=snapshot.id, qualified_name=name)
            )
        return tuple(references)

    async def commit(
        self, identity: QueryOperationIdentity, value: BatchQueryOutcome
    ) -> QueryOperationReceipt:
        row = await self.row(identity, lock=True)
        if row is None:
            raise conflict()
        previous = receipt_of(row)
        if previous is not None:
            if previous.result != value:
                raise conflict()
            return previous
        active = await self.session.scalar(
            select(Dataset.id)
            .where(
                Dataset.id == identity.dataset_id,
                Dataset.tenant_id == identity.tenant_id,
                Dataset.workspace_id == identity.workspace_id,
                Dataset.status == "ACTIVE",
            )
            .with_for_update(read=True)
        )
        if active is None:
            raise conflict()
        query = (
            (
                await self.session.execute(
                    select(
                        Query.question,
                        Query.executed_sql,
                        Query.execution_status,
                        Query.row_count,
                        Query.elapsed_ms,
                    ).where(
                        Query.id == value.query_id,
                        Query.tenant_id == identity.tenant_id,
                        Query.workspace_id == identity.workspace_id,
                        Query.dataset_id == identity.dataset_id,
                    )
                )
            )
            .mappings()
            .one_or_none()
        )
        if (
            query is None
            or query["question"] != identity.question
            or query["executed_sql"] != value.sql
            or query["execution_status"] != value.execution_status
            or query["row_count"] != value.row_count
            or query["elapsed_ms"] != value.elapsed_ms
            or value.knowledge_settings_snapshot.digest != identity.policy_sha256
        ):
            raise conflict()
        receipt = QueryOperationReceipt(
            identity=identity, result=value, snapshots=await self.snapshots(identity, value)
        )
        try:
            encoded = json.dumps(
                receipt.model_dump(mode="json"), ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
        except (ValueError, TypeError):
            raise conflict() from None
        if len(encoded.encode("utf-8")) > 1048576:
            raise PayloadTooLargeException("Query receipt exceeds1MiB", code="BULK_QUERY_RESULT_LIMIT")
        row.receipt_json = json.loads(encoded)
        row.query_id = value.query_id
        row.status = "committed"
        await self.session.flush()
        return receipt


@repository(name="knowledge.bulk_queries.native_repository")
class NativeQueryRepository:
    def __init__(self, resources: StructuredBulkRepository):
        self.resources = resources

    async def legacy_query_metadata(
        self, query_id: UUID, tenant_id: str, workspace_id: UUID
    ) -> dict[str, object] | None:
        async with self.read() as unit:
            row = await unit.session.execute(
                select(Query.id, Query.tenant_id, Query.workspace_id, Query.dataset_id).where(
                    Query.id == query_id,
                    Query.tenant_id == tenant_id,
                    Query.workspace_id == workspace_id,
                    ~exists(
                        select(NativeQueryOperation.id)
                        .where(NativeQueryOperation.query_id == Query.id)
                        .correlate(Query)
                    ),
                )
            )
            value = row.mappings().one_or_none()
            return dict(value) if value is not None else None

    @asynccontextmanager
    async def read(self) -> AsyncIterator[NativeQueryUnit]:
        async with infrastructure_unit(self.resources.native(), read_only=True) as session:
            yield NativeQueryUnit(session)

    @asynccontextmanager
    async def write(self) -> AsyncIterator[NativeQueryUnit]:
        async with infrastructure_unit(self.resources.native()) as session:
            yield NativeQueryUnit(session)
