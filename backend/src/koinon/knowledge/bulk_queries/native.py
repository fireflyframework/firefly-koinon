# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from pydantic import ValidationError
from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.bulk_queries.authority import QueryBatchAuthority
from koinon.knowledge.bulk_queries.dtos import BatchQueryOutcome
from koinon.knowledge.bulk_queries.entities import QueryBatchReference
from koinon.knowledge.bulk_queries.native_repository import NativeQueryRepository, receipt_of
from koinon.knowledge.bulk_queries.native_values import (
    NativeCommitDescriptor,
    QueryOperationIdentity,
    QueryOperationReceipt,
)
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

    async def inspect_commit_metadata(self, lease: QueryLease):
        with native_scope("structured", lease.tenant_id, lease.native_workspace_id, lease.subject):
            return await self.operations.inspect_commit_metadata(self.identity(lease))

    async def authorized_result(self, identity: QueryOperationIdentity, descriptor: NativeCommitDescriptor):
        """Hydrate only after the caller admits the descriptor's exact manifest."""
        with native_scope("structured", identity.tenant_id, str(identity.workspace_id), identity.subject):
            async with self.operations.read() as unit:
                status, observed = await self.operations.inspect_commit_metadata(identity)
                if status != "committed" or observed != descriptor:
                    raise ConflictException(
                        "Native commit metadata differs", code="BULK_QUERY_RECEIPT_CONFLICT"
                    )
                row = await unit.row(identity)
                receipt = receipt_of(row) if row is not None else None
                if receipt is None:
                    raise ConflictException("Native receipt unavailable", code="BULK_QUERY_RECEIPT_CONFLICT")
                return receipt

    @transactional
    async def acknowledge_commit_metadata(self, lease: QueryLease, descriptor: NativeCommitDescriptor):
        """Record an immutable native outcome without exercising source-reader rights."""
        descriptor = NativeCommitDescriptor.model_validate(descriptor)
        if descriptor.operation_id != UUID(lease.item_id):
            raise ConflictException("Query receipt owner differs", code="BULK_QUERY_RECEIPT_CONFLICT")
        await self.authority.shared.authority_lock(lease.tenant_id, lease.subject, lease.token_id)
        batch = await self.records.scoped(
            lease.tenant_id, lease.subject, lease.token_id, lease.batch_id, lock=True
        )
        item = await self.records.recovery_item(lease)
        job = await self.records.job(lease.job_id)
        if (
            batch is None
            or item is None
            or job is None
            or item.job_id != job.id
            or batch.workspace_id != lease.workspace_id
            or job.resource_id != lease.dataset_id
            or job.payload != {"batch_id": lease.batch_id, "item_id": lease.item_id}
            or job.attempts != lease.attempt
            or (job.worker_id is not None and job.worker_id != lease.worker_id)
        ):
            raise ConflictException("Query worker lost its current generation", code="BULK_LEASE_LOST")
        status, observed = await self.inspect_commit_metadata(lease)
        if status != "committed" or observed != descriptor:
            raise ConflictException("Native commit metadata differs", code="BULK_QUERY_RECEIPT_CONFLICT")
        encoded = descriptor.model_dump(mode="json", by_alias=True)
        if item.native_commit_json is not None:
            if item.native_commit_json != encoded:
                raise ConflictException(
                    "Query commit metadata is immutable", code="BULK_QUERY_RECEIPT_CONFLICT"
                )
            return
        if item.result_query_id is not None and item.result_query_id != str(descriptor.query_id):
            raise ConflictException("Query result identity differs", code="BULK_QUERY_RECEIPT_CONFLICT")
        await self.records.store_commit_metadata(item.id, descriptor)
        job.status, job.progress = descriptor.outcome, 100
        job.error = None if descriptor.outcome == "succeeded" else "BULK_QUERY_NOT_EXECUTED"
        job.lease_until = None
        job.worker_id = None
        job.result = {"batch_id": batch.id, "item_id": item.id, "dataset_id": item.dataset_id}
        batch.revision += 1
        await self.records.flush()

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
