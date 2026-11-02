# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime

from pyfly.container import service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.relational.sqlalchemy import Propagation, transactional
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, InvalidRequestException
from pyfly.security.context_holder import SecurityContextHolder

from koinon.knowledge.bulk.authority import BulkAuthority, execution_context
from koinon.knowledge.bulk.dtos import BulkDestination
from koinon.knowledge.bulk.entities import BulkTableReservation
from koinon.knowledge.bulk.recovery_intent import recovery_operation
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.bulk.structured_dtos import StructuredTablePlan


@dataclass(frozen=True)
class BulkLease:
    job_id: str
    item_id: str
    batch_id: str
    tenant_id: str
    subject: str
    token_id: str | None
    worker_id: str
    attempt: int
    source_id: str
    asset_id: str
    filename: str
    size_bytes: int
    sha256: str
    mode: str
    destination: BulkDestination
    expires_at: datetime | None = None
    recovery_operation: str | None = None


@dataclass(frozen=True)
class BulkOriginal:
    object_key: str = field(repr=False)
    size_bytes: int
    sha256: str
    storage_identity: str | None = None
    object_reference_json: dict | None = None


@service(name="knowledge.bulk.queue")
class BulkQueue:
    def __init__(
        self,
        records: BulkRepository,
        authority: BulkAuthority,
        settings: BulkSettings,
        datasources: DataSourceRegistry,
    ):
        self.records, self.authority, self.settings, self.datasources = (
            records,
            authority,
            settings,
            datasources,
        )

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def claim(self, worker_id: str) -> BulkLease | None:
        self.settings.validate()
        if not worker_id or len(worker_id) > 64:
            raise InvalidRequestException("Use a bounded worker identity", code="INVALID_WORKER")
        claimed = await self.records.claim(
            worker_id,
            self.settings.lease_seconds,
            self.settings.max_workers_global,
            self.settings.max_workers_per_tenant,
        )
        if claimed is None:
            return None
        return self._lease(*claimed)

    @staticmethod
    def _lease(job, item, batch) -> BulkLease:
        return BulkLease(
            job_id=job.id,
            item_id=item.id,
            batch_id=batch.id,
            tenant_id=batch.tenant_id,
            subject=batch.subject,
            token_id=batch.token_id,
            worker_id=job.worker_id or "",
            attempt=job.attempts,
            recovery_operation=recovery_operation(job, item, batch),
            source_id=item.source_id,
            asset_id=item.asset_id,
            filename=item.filename,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
            mode=item.mode,
            destination=BulkDestination(
                workspace_id=batch.workspace_id, project_id=batch.project_id, parent_id=batch.parent_id
            ),
            expires_at=job.lease_until,
        )

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def load_claimed(self, item_id: str, worker_id: str, attempt: int) -> BulkLease:
        lease = self._lease(*await self.records.claimed(item_id, worker_id, attempt))
        await self._check(lease)
        return lease

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def reserve_tables(
        self, lease: BulkLease, plans: tuple[StructuredTablePlan, ...]
    ) -> tuple[StructuredTablePlan, ...]:
        if (
            not 1 <= len(plans) <= 16
            or tuple(p.ordinal for p in plans) != tuple(range(len(plans)))
            or len({p.table_id for p in plans}) != len(plans)
            or len({p.snapshot_id for p in plans}) != len(plans)
            or len({p.name for p in plans}) != len(plans)
        ):
            raise ConflictException("Use a complete bounded table plan", code="BULK_TABLE_LIMIT")
        with SecurityContextHolder.using(execution_context(lease.subject, lease.token_id)):
            await self._check(lease)
            _, item, batch = await self.records.fenced(
                lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt
            )
            if item.mode != "dataset":
                raise ConflictException("Only datasets reserve tables", code="BULK_MODE_UNAVAILABLE")
            rows = await self.records.table_reservations(item.id)
            if rows:
                if len(rows) != len(plans) or any(
                    (row.ordinal, row.table_id, row.snapshot_id, row.name)
                    != (plan.ordinal, str(plan.table_id), str(plan.snapshot_id), plan.name)
                    for row, plan in zip(rows, plans, strict=True)
                ):
                    raise ConflictException(
                        "Reserved tables cannot be replaced", code="BULK_NATIVE_RECEIPT_CONFLICT"
                    )
            else:
                for plan in plans:
                    table = await self.authority.catalog.create(
                        lease.subject,
                        lease.tenant_id,
                        kind="table",
                        name=plan.name,
                        parent_id=item.asset_id,
                        metadata={"snapshot_id": str(plan.snapshot_id), "bulk_item_id": item.id},
                    )
                    await self.authority.catalog.update(
                        lease.subject, lease.tenant_id, table.id, {"status": "pending"}
                    )
                    await self.records.add_table_reservation(
                        BulkTableReservation(
                            item_id=item.id,
                            ordinal=plan.ordinal,
                            table_id=str(plan.table_id),
                            snapshot_id=str(plan.snapshot_id),
                            catalog_table_id=table.id,
                            name=plan.name,
                        )
                    )
                batch.revision += 1
                rows = await self.records.table_reservations(item.id)
            return tuple(
                plan.model_copy(update={"catalog_table_id": row.catalog_table_id})
                for plan, row in zip(plans, rows, strict=True)
            )

    async def _check(self, lease: BulkLease) -> None:
        with SecurityContextHolder.using(execution_context(lease.subject, lease.token_id)):
            await self.authority.destination(lease.subject, lease.tenant_id, lease.destination, write=True)
            await self.authority.item(
                lease.subject,
                lease.tenant_id,
                lease.source_id,
                lease.asset_id,
                lease.destination,
                lease.sha256,
            )
            candidate = await self.records.item(lease.batch_id, lease.item_id)
            if candidate is None:
                raise ConflictException("Reserved item is unavailable", code="BULK_LEASE_LOST")
            if candidate.mode == "dataset":
                await self.authority.dataset(lease.subject, lease.tenant_id, candidate, lease.destination)
            job, item, batch = await self.records.fenced(
                lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt
            )
            if recovery_operation(job, item, batch) != lease.recovery_operation:
                raise ConflictException("Recovery action changed", code="BULK_RECOVERY_STATE_CHANGED")
            if item.connection_json != await self.records.connection(
                batch.tenant_id, batch.workspace_id, item.mode
            ):
                raise ConflictException(
                    "The admitted embedding connection changed", code="BULK_CONNECTION_CHANGED"
                )
            if item.native_workspace_id and not await self.records.workspace_matches(
                batch.tenant_id,
                batch.workspace_id,
                "canon" if item.mode == "document" else "structured",
                item.native_workspace_id,
            ):
                raise ConflictException("Reserved native workspace changed", code="BULK_NATIVE_SCOPE_CHANGED")

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def check(self, lease: BulkLease) -> None:
        await self._check(lease)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def original(self, lease: BulkLease) -> BulkOriginal:
        await self._check(lease)
        _, item, _ = await self.records.fenced(lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt)
        upload = await self.records.upload_by_id(item.winning_upload_id) if item.winning_upload_id else None
        if upload is None or upload.item_id != item.id or upload.status != "verified":
            raise ConflictException(
                "Original has no verified durable receipt", code="BULK_ORIGINAL_UNAVAILABLE"
            )
        state = await self.records.upload_state(upload.id)
        return BulkOriginal(
            upload.object_key,
            item.size_bytes,
            item.sha256,
            state.storage_identity if state else None,
            upload.object_reference_json,
        )

    @asynccontextmanager
    async def publication(self, lease: BulkLease) -> AsyncIterator[None]:
        async with infrastructure_unit(self.datasources.get("primary")):
            await self._check(lease)
            yield
            await self.records.fenced(lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def failed(self, lease: BulkLease, *, code: str, unknown: bool) -> None:
        job, item, batch = await self.records.fenced(
            lease.tenant_id, lease.item_id, lease.worker_id, lease.attempt
        )
        item.status = "reconciling" if unknown else "failed"
        item.error_code = (
            code
            if code.isascii() and code.replace("_", "").isalnum() and len(code) <= 64
            else "BULK_PROCESSING_FAILED"
        )
        job.status = "failed"
        job.error = item.error_code
        job.lease_until = None
        job.worker_id = None
        batch.revision += 1
        await self.records.flush()
