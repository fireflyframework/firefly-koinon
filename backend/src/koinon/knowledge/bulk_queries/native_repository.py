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
from sqlalchemy import exists, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository
from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
from koinon.knowledge.bulk_queries.native_entities import NativeQueryOperation
from koinon.knowledge.bulk_queries.native_values import (
    NativeCommitDescriptor,
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
                        Query.table_id_snapshot_pins_json,
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
        manifest = query["table_id_snapshot_pins_json"]
        if not isinstance(manifest, dict) or len(manifest) > 500:
            raise conflict()
        try:
            if any(str(UUID(key)) != key or str(UUID(pin)) != pin for key, pin in manifest.items()):
                raise conflict()
        except (TypeError, ValueError, AttributeError):
            raise conflict() from None
        snapshots = await self.snapshots(identity, value)
        if any(manifest.get(str(pin.table_id)) != str(pin.snapshot_id) for pin in snapshots):
            raise conflict()
        receipt = QueryOperationReceipt(
            identity=identity, result=value, snapshots=snapshots, source_manifest=manifest
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

    async def inspect_commit_metadata(self, identity: QueryOperationIdentity):
        """Project immutable commit facts without hydrating any protected result."""
        async with self.read() as unit:
            row = (
                (
                    await unit.session.execute(
                        text("""
                SELECT o.status,
                  (o.tenant_id=:tenant AND o.subject=:subject AND o.workspace_id=:workspace
                   AND o.dataset_id=:dataset AND o.catalog_workspace_id=:catalog_workspace
                   AND o.catalog_dataset_id=:catalog_dataset AND o.question=:question
                   AND o.policy_sha256=:policy AND o.connections_sha256=:connections
                   AND (o.status='admitted' OR (
                     o.status='committed' AND q.id=o.query_id AND q.tenant_id=o.tenant_id
                     AND q.workspace_id=o.workspace_id AND q.dataset_id=o.dataset_id
                     AND q.finalised_at IS NOT NULL
                     AND o.receipt_json::jsonb->'identity'=CAST(:identity AS jsonb)
                     AND o.receipt_json::jsonb->'result'->>'query_id'=q.id::text
                     AND o.receipt_json::jsonb->'result'->>'execution_status'=q.execution_status
                     AND o.receipt_json::jsonb->'source_manifest'=q.table_id_snapshot_pins_json
                     AND jsonb_typeof(o.receipt_json::jsonb->'source_manifest')='object'
                     AND q.execution_status IN ('OK','REFINED_OK','FAILED','REJECTED_BY_FIREWALL')
                   ))) AS valid,
                  o.id AS operation_id,o.query_id,
                  public.koinon_json_sha256(o.receipt_json::jsonb->'identity') AS identity_sha256,
                  public.koinon_json_sha256(o.receipt_json::jsonb) AS receipt_sha256,
                  public.koinon_json_sha256(o.receipt_json::jsonb->'source_manifest') AS manifest_sha256,
                  CASE WHEN q.execution_status IN ('OK','REFINED_OK')
                    THEN 'succeeded' ELSE 'failed' END AS outcome
                FROM flyquery_bulk_query_operations o
                LEFT JOIN flyquery_queries q ON q.id=o.query_id
                WHERE o.id=:operation AND o.tenant_id=:tenant
            """),
                        {
                            "operation": identity.operation_id,
                            "tenant": identity.tenant_id,
                            "subject": identity.subject,
                            "workspace": identity.workspace_id,
                            "dataset": identity.dataset_id,
                            "catalog_workspace": identity.catalog_workspace_id,
                            "catalog_dataset": identity.catalog_dataset_id,
                            "question": identity.question,
                            "policy": identity.policy_sha256,
                            "connections": identity.connections_sha256,
                            "identity": json.dumps(identity.model_dump(mode="json")),
                        },
                    )
                )
                .mappings()
                .one_or_none()
            )
        if row is None:
            return "absent", None
        if row["valid"] is not True:
            raise conflict()
        if row["status"] == "admitted":
            return "admitted", None
        try:
            descriptor = NativeCommitDescriptor.model_validate(
                {key: row[key] for key in NativeCommitDescriptor.model_fields if key != "schema_"}
            )
        except ValidationError:
            raise conflict() from None
        return "committed", descriptor

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
