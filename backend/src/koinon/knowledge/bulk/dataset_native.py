# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native dataset receipts share the existing Structured lifecycle and model scopes."""

from contextlib import asynccontextmanager
from uuid import UUID

from flyquery.core.services.ingestion import lineage
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
from koinon.knowledge.bulk.structured_repository import (
    SourceStructuredReceiptIdentity,
    StructuredBulkRepository,
)
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

    @asynccontextmanager
    async def producer(self, lease, identity, *, resume=False):
        providers = getattr(self.queue, "source_writers", None)
        writer = providers.get() if providers is not None else None
        admission = await writer.admission_for(lease) if writer is not None else None
        if writer is not None and admission is not None:
            async with writer.structured_producer(
                admission,
                execution=lease,
                operation=identity,
                publication=lambda: self.queue.publication(lease),
            ) as producer:
                with lineage.observe(producer):
                    yield producer
            return
        if resume:
            yield None
            return
        facade = self.facades.get()
        if facade is None:
            raise ServiceUnavailableException(
                "Native dataset resources unavailable", code="BULK_NATIVE_REQUIRED"
            )
        async with facade.domains.structured_lineage(
            tenant_id=lease.tenant_id,
            workspace_id=str(identity.workspace_id),
            actor=lease.subject,
            catalog_workspace_id=lease.destination.workspace_id,
            dataset_id=str(identity.dataset_id),
            source_catalog_id=lease.source_id,
            operation="upload",
        ):
            yield None

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
            source_attempt_id=receipt.source_attempt_id,
            source_publication_sha256=receipt.source_publication_sha256,
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
                return await unit.inspect_receipt(identity)

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def source_receipt_identity(self, lease: BulkLease) -> SourceStructuredReceiptIdentity | None:
        if not await self.records.source_owned(lease.tenant_id, lease.item_id):
            return None
        row = await self.records.source_receipt_reservation(
            lease.tenant_id,
            lease.subject,
            lease.batch_id,
            lease.item_id,
        )
        if (
            row is None
            or row.mode != "dataset"
            or (row.source_id, row.asset_id, row.sha256, row.size_bytes)
            != (lease.source_id, lease.asset_id, lease.sha256, lease.size_bytes)
        ):
            raise ConflictException("Source dataset reservation differs", code="BULK_NATIVE_RECEIPT_CONFLICT")
        try:
            return SourceStructuredReceiptIdentity(
                operation_id=UUID(row.id),
                tenant_id=lease.tenant_id,
                workspace_id=UUID(row.native_workspace_id),
                dataset_id=UUID(row.dataset_id),
                file_id=UUID(row.file_id),
                actor=lease.subject,
                catalog_source_id=row.source_id,
                catalog_dataset_id=row.asset_id,
                catalog_file_version_id=row.catalog_file_version_id,
                sha256=row.sha256,
                size_bytes=row.size_bytes,
                source_attempt_id=row.source_attempt_id,
                source_publication_sha256=row.source_publication_sha256,
            )
        except (TypeError, ValueError, AttributeError):
            raise ConflictException(
                "Source dataset reservation differs",
                code="BULK_NATIVE_RECEIPT_CONFLICT",
            ) from None

    async def inspect_committed(self, lease: BulkLease) -> NativeObservation:
        identity = await self.source_receipt_identity(lease)
        if identity is None:
            return await self.inspect(lease)
        with native_scope("structured", lease.tenant_id, str(identity.workspace_id), lease.subject):
            async with self.operations.read() as unit:
                return await unit.inspect_source_receipt(identity)

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
            self.producer(lease, identity) as producer,
        ):
            arguments = {"_source_producer": producer} if producer is not None else {}
            await self.pipeline.prepare(lease, identity, content, **arguments)
            return self.receipt(await self.pipeline.finalize(lease, identity, **arguments))

    async def finalize_prepared(self, lease: BulkLease) -> NativeCommit:
        identity = await self.identity(lease)
        with native_scope("structured", lease.tenant_id, str(identity.workspace_id), lease.subject):
            async with self.producer(lease, identity, resume=True) as producer:
                arguments = {"_source_producer": producer} if producer is not None else {}
                return self.receipt(await self.pipeline.finalize(lease, identity, **arguments))
