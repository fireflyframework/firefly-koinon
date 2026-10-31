# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native dataset receipts share the existing Structured lifecycle and model scopes."""

from uuid import UUID

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import Isolation, Propagation, transactional
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
from koinon.knowledge.bulk.ports import NativeCommit, NativeObservation, NativeTableCommit
from koinon.knowledge.bulk.queue import BulkLease, BulkQueue
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.bulk.structured_dtos import StructuredOperationIdentity, StructuredOperationState
from koinon.knowledge.bulk.structured_pipeline import StructuredBulkPipeline
from koinon.knowledge.bulk.structured_repository import StructuredBulkRepository
from koinon.knowledge.service import KnowledgeFacade
from koinon.security.authority import PRIMARY_POLICY_UNIT


@service(name="knowledge.bulk.dataset_native")
class DatasetBulkNative:
    def __init__(
        self,
        operations: StructuredBulkRepository,
        pipeline: StructuredBulkPipeline,
        records: BulkRepository,
        queue: BulkQueue,
        facades: Provider[KnowledgeFacade | None],
    ):
        self.operations, self.pipeline, self.records, self.queue, self.facades = (
            operations,
            pipeline,
            records,
            queue,
            facades,
        )

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def identity(self, lease: BulkLease) -> StructuredOperationIdentity:
        item = await self.records.item(lease.batch_id, lease.item_id)
        if (
            item is None
            or item.mode != "dataset"
            or not item.native_workspace_id
            or item.source_id != lease.source_id
            or item.asset_id != lease.asset_id
            or item.filename != lease.filename
            or item.sha256 != lease.sha256
            or item.size_bytes != lease.size_bytes
        ):
            raise ConflictException("Reserved dataset differs", code="BULK_NATIVE_RECEIPT_CONFLICT")
        reservation = DatasetReservation.stored(item.reservation_json)
        return StructuredOperationIdentity(
            operation_id=UUID(item.id),
            tenant_id=lease.tenant_id,
            workspace_id=UUID(item.native_workspace_id),
            dataset_id=reservation.native_dataset_id,
            file_id=reservation.native_file_id,
            actor=lease.subject,
            catalog_source_id=lease.source_id,
            catalog_dataset_id=lease.asset_id,
            catalog_file_version_id=reservation.catalog_file_version_id,
            filename=lease.filename,
            sha256=lease.sha256,
            size_bytes=lease.size_bytes,
        )

    @staticmethod
    def receipt(state: StructuredOperationState) -> NativeCommit:
        receipt = state.receipt
        if state.status != "committed" or receipt is None:
            raise ConflictException(
                "Dataset has no complete commit receipt", code="BULK_NATIVE_RECEIPT_REQUIRED"
            )
        return NativeCommit(
            domain="structured",
            native_workspace_id=str(state.identity.workspace_id),
            native_source_id=str(receipt.dataset_id),
            native_asset_id=str(receipt.dataset_id),
            sha256=receipt.sha256,
            size_bytes=receipt.size_bytes,
            object_key=receipt.object_key,
            file_version_id=state.identity.catalog_file_version_id,
            native_file_id=str(receipt.file_id),
            tables=tuple(
                NativeTableCommit(
                    catalog_table_id=t.catalog_table_id,
                    table_id=str(t.table_id),
                    snapshot_id=str(t.snapshot_id),
                    n_columns=t.n_columns,
                    n_rows_actual=t.n_rows_actual,
                )
                for t in receipt.tables
            ),
        )

    async def inspect(self, lease: BulkLease) -> NativeObservation:
        identity = await self.identity(lease)
        with native_scope("structured", lease.tenant_id, str(identity.workspace_id), lease.subject):
            async with self.operations.read() as unit:
                state = await unit.get(identity)
        if state is None:
            return NativeObservation("absent")
        return NativeObservation(state.status, self.receipt(state) if state.status == "committed" else None)

    async def execute(self, lease: BulkLease, content: bytes) -> NativeCommit:
        identity = await self.identity(lease)
        facade = self.facades.get()
        if facade is None:
            raise ServiceUnavailableException(
                "Native dataset resources unavailable", code="BULK_NATIVE_REQUIRED"
            )
        async with (
            facade.domains.model_connections(
                "structured",
                lease.tenant_id,
                str(identity.workspace_id),
                lease.subject,
                purpose="ingest",
                roles=("structured.embedding",),
                catalog_workspace_id=lease.destination.workspace_id,
            ),
            facade.domains.structured_lineage(
                tenant_id=lease.tenant_id,
                workspace_id=str(identity.workspace_id),
                actor=lease.subject,
                catalog_workspace_id=lease.destination.workspace_id,
                dataset_id=str(identity.dataset_id),
                source_catalog_id=lease.source_id,
                operation="upload",
            ),
        ):
            await self.pipeline.prepare(lease, identity, content)
            return self.receipt(await self.pipeline.finalize(lease, identity))

    async def finalize_prepared(self, lease: BulkLease) -> NativeCommit:
        identity = await self.identity(lease)
        with native_scope("structured", lease.tenant_id, str(identity.workspace_id), lease.subject):
            return self.receipt(await self.pipeline.finalize(lease, identity))
