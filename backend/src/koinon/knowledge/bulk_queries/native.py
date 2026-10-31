# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import Propagation, transactional
from pyfly.kernel import ConflictException

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.bulk.authority import token_identity
from koinon.knowledge.bulk_queries.authority import QueryBatchAuthority
from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
from koinon.knowledge.bulk_queries.entities import QueryBatchReference
from koinon.knowledge.bulk_queries.native_repository import NativeQueryRepository, receipt_of
from koinon.knowledge.bulk_queries.native_values import QueryOperationIdentity, QueryOperationReceipt
from koinon.knowledge.bulk_queries.queue import QueryBatchQueue, QueryLease
from koinon.knowledge.bulk_queries.repositories import QueryBatchRepository
from koinon.knowledge.capture_receipt import NativeEvidenceReceipt
from koinon.organization_knowledge.runtime import bind_snapshot


@service(name="knowledge.bulk_queries.native")
class BulkQueryNative:
    def __init__(
        self,
        operations: NativeQueryRepository,
        queue: QueryBatchQueue,
        records: QueryBatchRepository,
        authority: QueryBatchAuthority,
    ):
        self.operations, self.queue, self.records, self.authority = operations, queue, records, authority

    @staticmethod
    def identity(lease: QueryLease) -> QueryOperationIdentity:
        return QueryOperationIdentity(
            operation_id=UUID(lease.item_id),
            tenant_id=lease.tenant_id,
            subject=lease.subject,
            workspace_id=UUID(lease.native_workspace_id),
            dataset_id=UUID(lease.native_dataset_id),
            catalog_workspace_id=lease.workspace_id,
            catalog_dataset_id=lease.dataset_id,
            question=lease.question,
            policy_sha256=lease.policy.digest,
            connections_sha256=lease.connections_sha256,
        )

    async def inspect(self, lease: QueryLease) -> tuple[str, QueryOperationReceipt | None]:
        identity = self.identity(lease)
        with native_scope("structured", lease.tenant_id, lease.native_workspace_id, lease.subject):
            async with self.operations.read() as unit:
                row = await unit.row(identity)
                return (row.status, receipt_of(row)) if row is not None else ("absent", None)

    async def _references(self, lease: QueryLease, receipt: QueryOperationReceipt) -> None:
        item = await self.records.item(lease.batch_id, lease.item_id)
        if item is None:
            raise ConflictException("Query item unavailable", code="BULK_QUERY_SCOPE_CHANGED")
        current = []
        for value in receipt.snapshots:
            table = await self.authority.snapshot_alias(
                lease.subject, lease.tenant_id, lease.workspace_id, item, value
            )
            current.append((table.id, str(value.table_id), str(value.snapshot_id), value.qualified_name))
        previous = await self.records.references(item.id)
        if previous:
            if sorted(
                (r.catalog_id, r.native_table_id, r.snapshot_id, r.qualified_name) for r in previous
            ) != sorted(current):
                raise ConflictException(
                    "Saved query references are immutable", code="BULK_QUERY_RECEIPT_CONFLICT"
                )
        else:
            for catalog_id, native_table_id, snapshot_id, qualified_name in current:
                await self.records.add_reference(
                    QueryBatchReference(
                        item_id=item.id,
                        catalog_id=catalog_id,
                        native_table_id=native_table_id,
                        snapshot_id=snapshot_id,
                        qualified_name=qualified_name,
                    )
                )

    async def execute(self, lease: QueryLease) -> QueryOperationReceipt:
        await self.queue.check(lease)
        identity = self.identity(lease)
        evidence = NativeEvidenceReceipt(lease.subject, lease.tenant_id)
        committed: QueryOperationReceipt | None = None
        with (
            native_scope("structured", lease.tenant_id, lease.native_workspace_id, lease.subject),
            bind_snapshot(lease.policy, lease.subject),
        ):
            async with self.queue.publication(lease), self.operations.write() as unit:
                await unit.admit(identity)

            async def commit(raw):
                nonlocal committed
                try:
                    value = BatchQueryOutcome.model_validate(raw)
                except ValidationError:
                    raise ConflictException(
                        "Native query response cannot be verified", code="BULK_QUERY_RECEIPT_CONFLICT"
                    ) from None
                async with self.operations.write() as unit:
                    receipt = await unit.commit(identity, value)
                    committed = receipt
                    await self._references(lease, receipt)

            try:
                await self.authority.facade().query(
                    lease.subject,
                    lease.tenant_id,
                    dataset_id=lease.dataset_id,
                    question=lease.question,
                    _capture=evidence,
                    _query_commit=commit,
                    _query_publication_guard=lambda: self.queue.publication(lease),
                    _query_authorize=lambda: self.queue.check(lease),
                )
            finally:
                evidence.closed = True
        if committed is None:
            raise ConflictException(
                "Native query lacks a complete receipt", code="BULK_QUERY_RECEIPT_REQUIRED"
            )
        return committed

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def acknowledge(self, lease: QueryLease, receipt: QueryOperationReceipt) -> None:
        await self.authority.workspace(lease.subject, lease.tenant_id, lease.workspace_id, write=True)
        item = await self.records.item(lease.batch_id, lease.item_id)
        if item is None:
            raise ConflictException("Query item unavailable", code="BULK_QUERY_SCOPE_CHANGED")
        await self.authority.item(lease.subject, lease.tenant_id, lease.workspace_id, item, write=True)
        await self.records.fenced(lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt)
        await self.acknowledge_committed(lease, receipt)

    @transactional
    async def acknowledge_committed(self, lease: QueryLease, receipt: QueryOperationReceipt) -> None:
        await self.authority.workspace(lease.subject, lease.tenant_id, lease.workspace_id, write=True)
        candidate = await self.records.item(lease.batch_id, lease.item_id)
        if candidate is None:
            raise ConflictException("Query item unavailable", code="BULK_QUERY_SCOPE_CHANGED")
        await self.authority.item(lease.subject, lease.tenant_id, lease.workspace_id, candidate, write=True)
        batch = await self.records.scoped(
            lease.tenant_id, lease.subject, token_identity(), lease.batch_id, lock=True
        )
        item = await self.records.item(lease.batch_id, lease.item_id, lock=True)
        if batch is None or item is None or receipt.identity != self.identity(lease):
            raise ConflictException("Query receipt owner differs", code="BULK_QUERY_RECEIPT_CONFLICT")
        if item.result_json is not None:
            if item.result_json != receipt.result.model_dump(mode="json"):
                raise ConflictException("Query result is immutable", code="BULK_QUERY_RECEIPT_CONFLICT")
            return
        status, observed = await self.inspect(lease)
        if status != "committed" or observed != receipt:
            raise ConflictException(
                "Only an existing native query commit may be acknowledged", code="BULK_QUERY_RECEIPT_CONFLICT"
            )
        await self._references(lease, receipt)
        job = await self.records.job(item.job_id)
        if job is None:
            raise ConflictException("Query job unavailable", code="BULK_QUERY_RECEIPT_CONFLICT")
        item.result_json = receipt.result.model_dump(mode="json")
        item.status = "succeeded" if receipt.result.execution_status in {"OK", "REFINED_OK"} else "failed"
        item.error_code = (
            None
            if item.status == "succeeded"
            else "BULK_QUERY_CLARIFICATION_REQUIRED"
            if receipt.result.clarification
            else "BULK_QUERY_NOT_EXECUTED"
        )
        job.status = item.status
        job.progress = 100
        job.error = item.error_code
        job.lease_until = None
        job.worker_id = None
        job.result = {"batch_id": batch.id, "item_id": item.id, "dataset_id": item.dataset_id}
        batch.revision += 1
        await self.records.flush()
