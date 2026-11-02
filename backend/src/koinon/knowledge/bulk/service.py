# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded staged originals and durable per-item admission; SQL stays in native repositories."""

import asyncio
import hashlib
import json
import secrets
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import dataclass, field, replace
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from koinon_storage.files import source_file
from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import Isolation, Propagation, transactional
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import (
    ConflictException,
    ForbiddenException,
    GoneException,
    InvalidRequestException,
    PayloadTooLargeException,
    RateLimitException,
    ServiceUnavailableException,
)
from pyfly.security.context_holder import SecurityContextHolder

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.jobs.service import JobService
from koinon.knowledge.bulk.authority import BulkAuthority, execution_context, token_identity
from koinon.knowledge.bulk.dataset_dtos import DatasetReservation
from koinon.knowledge.bulk.dtos import (
    BulkAction,
    BulkDestination,
    BulkRecoveryAction,
    FileBatchCapabilities,
    FileBatchCreate,
    FileBatchItemView,
    FileBatchPage,
    FileBatchView,
    FileItemPage,
    FileRecoveryView,
    NativeRecoveryState,
    RecoveryOperation,
    StagedFileReceipt,
    aggregate_status,
)
from koinon.knowledge.bulk.entities import BulkBatch, BulkItem, BulkRecovery, BulkUpload, BulkUploadState, now
from koinon.knowledge.bulk.ports import BulkIntakePort
from koinon.knowledge.bulk.queue import BulkQueue
from koinon.knowledge.bulk.recovery_intent import PENDING_RECOVERY, ProcessingRecoveryIntent
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.bulk.settings import BulkSettings
from koinon.knowledge.bulk.storage import BulkStorage, LocalWriterPermit
from koinon.security.authority import PRIMARY_POLICY_UNIT


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def key_digest(key: str) -> str:
    if not isinstance(key, str) or not key.strip() or len(key) > 255:
        raise InvalidRequestException(
            "Idempotency-Key requires 1 to 255 characters", code="BULK_KEY_REQUIRED"
        )
    return digest(["bulk:v1", key])


@dataclass(frozen=True)
class UploadTicket:
    upload_id: str
    object_key: str = field(repr=False)
    size_bytes: int
    sha256: str
    write: bool
    local_permit: LocalWriterPermit | None = field(default=None, repr=False, compare=False)
    writer_token: str = field(default="", repr=False)
    generation: int = 0
    storage_identity: str = field(default="", repr=False)


@dataclass(frozen=True)
class RecoveryTicket:
    upload: UploadTicket
    action_id: str
    token: str = field(repr=False)
    generation: int
    fenced_revision: int


@service(name="knowledge.bulk.files")
class FileBatches:
    def __init__(
        self,
        catalog: CatalogService,
        records: BulkRepository,
        storage: BulkStorage,
        settings: BulkSettings,
        jobs: JobService,
        authority: BulkAuthority,
        intakes: Provider[BulkIntakePort | None] | None = None,
    ):
        self.catalog, self.records, self.storage, self.settings, self.jobs, self.authority = (
            catalog,
            records,
            storage,
            settings,
            jobs,
            authority,
        )

        self.intakes = intakes

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def capabilities(self, subject: str, tenant: str, workspace_id: str) -> FileBatchCapabilities:
        self.settings.validate()
        workspace = await self.catalog.get(subject, tenant, workspace_id)
        if workspace.kind != "workspace" or workspace.status == "archived":
            raise AccessDenied("Selected workspace is unavailable", code="ACCESS_DENIED")
        configured = True
        try:
            self.storage.configured()
        except ServiceUnavailableException:
            configured = False
        if self.storage.effective_file_limit() < 1:
            configured = False
        backend = self.settings.storage_backend
        return FileBatchCapabilities(
            configured=configured,
            staging_backend=(
                "private_local_posix"
                if backend == "local"
                else "private_azure_blob"
                if backend == "azure"
                else "private_gcs_object"
            ),
            staging_topology=(
                "single_host_shared_durable_posix" if backend == "local" else "shared_private_object_store"
            ),
            modes=["document", "dataset"],
            max_files=self.settings.max_files,
            max_file_bytes=self.storage.effective_file_limit(),
            max_batch_bytes=self.settings.max_batch_bytes,
            max_active_batches_per_subject=self.settings.max_active_batches_per_subject,
        )

    async def _scope(self, subject: str, tenant: str, identifier: str, *, write: bool = False) -> BulkBatch:
        if write:
            await self.records.authority_lock(tenant, subject, token_identity())
        row = await self.records.scoped(tenant, subject, identifier, lock=write)
        if row is None or row.token_id != token_identity():
            raise AccessDenied("Private intake batch is unavailable", code="ACCESS_DENIED")
        await self.authority.destination(
            subject,
            tenant,
            BulkDestination(
                workspace_id=row.workspace_id, project_id=row.project_id, parent_id=row.parent_id
            ),
            write=write,
        )
        if not write:
            for item in await self.records.all_items(row.id):
                await self.catalog.get(subject, tenant, item.asset_id)
        return row

    async def _view(self, row: BulkBatch) -> FileBatchView:
        counts = await self.records.counts(row.id)
        return FileBatchView(
            id=row.id,
            tenant_id=row.tenant_id,
            destination=BulkDestination(
                workspace_id=row.workspace_id, project_id=row.project_id, parent_id=row.parent_id
            ),
            status="expired"
            if not row.submitted and not row.cancelled and row.expires_at <= now()
            else aggregate_status([key for key, value in counts.items() if value]),
            revision=row.revision,
            total_items=sum(counts.values()),
            total_bytes=row.total_bytes,
            counts=counts,
            cancellation_requested=row.cancelled,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )

    async def _item_for_write(self, subject: str, tenant: str, row: BulkBatch, item_id: str) -> BulkItem:
        item = await self.records.item(row.id, item_id)
        if item is None:
            raise AccessDenied("Intake item is unavailable", code="ACCESS_DENIED")
        await self.authority.item(
            subject,
            tenant,
            item.source_id,
            item.asset_id,
            BulkDestination(
                workspace_id=row.workspace_id, project_id=row.project_id, parent_id=row.parent_id
            ),
            item.sha256,
        )
        if item.mode == "dataset":
            await self.authority.dataset(
                subject,
                tenant,
                item,
                BulkDestination(
                    workspace_id=row.workspace_id, project_id=row.project_id, parent_id=row.parent_id
                ),
            )
        current = await self.records.item(row.id, item_id, lock=True)
        if current is None:
            raise AccessDenied("Intake item is unavailable", code="ACCESS_DENIED")
        return current

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def create(self, subject: str, tenant: str, request: FileBatchCreate, key: str) -> FileBatchView:
        request = FileBatchCreate.model_validate(request.model_dump(mode="python")).model_copy(deep=True)
        self.settings.validate()
        key_hash = key_digest(key)
        total = sum(item.size_bytes for item in request.items)
        if (
            len(request.items) > self.settings.max_files
            or total > self.settings.max_batch_bytes
            or any(item.size_bytes > self.storage.effective_file_limit() for item in request.items)
        ):
            raise PayloadTooLargeException(
                "Bulk manifest exceeds configured bounds", code="BULK_MANIFEST_LIMIT"
            )
        await self.authority.destination(subject, tenant, request.destination, write=True)
        self.storage.configured()
        previous = await self.records.keyed(tenant, key_hash)
        request_hash = digest([subject, token_identity(), request.model_dump(mode="json")])
        if previous:
            if previous.request_hash != request_hash:
                raise ConflictException("Key belongs to a different admission", code="IDEMPOTENCY_CONFLICT")
            return await self._view(await self._scope(subject, tenant, previous.id))
        quota = await self.records.quota("tenant:" + tenant)
        history, active, actor_active = await self.records.admission_counts(tenant, subject)
        if history >= self.settings.max_batches_per_tenant:
            raise RateLimitException("Retained batch metadata reached its bound", code="BULK_HISTORY_LIMIT")
        if (
            active >= self.settings.max_active_batches_per_tenant
            or actor_active >= self.settings.max_active_batches_per_subject
        ):
            raise RateLimitException("Active batch admission is full", code="BULK_BATCH_LIMIT")
        if quota.reserved_bytes + total > self.settings.max_staged_bytes_per_tenant:
            raise RateLimitException("Retained staged bytes exceed tenant quota", code="BULK_QUOTA_EXCEEDED")
        row = BulkBatch(
            id=str(uuid4()),
            tenant_id=tenant,
            subject=subject,
            token_id=token_identity(),
            **request.destination.model_dump(),
            key_hash=key_hash,
            request_hash=request_hash,
            request_json=request.model_dump(mode="json"),
            actions_json={},
            revision=1,
            total_bytes=total,
            created_at=now(),
            expires_at=now() + timedelta(hours=self.settings.staging_hours),
        )
        row = await self.records.save(row)
        for ordinal, item in enumerate(request.items):
            item_id = str(uuid4())
            metadata = {"sha256": item.sha256, "bytes": item.size_bytes, "mode": item.mode}
            source = await self.catalog.create(
                subject, tenant, kind="source", name=item.filename, parent_id=row.parent_id, metadata=metadata
            )
            await self.catalog.update(subject, tenant, source.id, {"status": "pending"})
            asset = await self.catalog.create(
                subject,
                tenant,
                kind=item.mode,
                name=item.filename,
                parent_id=source.id,
                metadata={"sha256": item.sha256},
            )
            await self.catalog.update(subject, tenant, asset.id, {"status": "pending"})
            reservation = None
            if item.mode == "dataset":
                version = await self.catalog.create(
                    subject,
                    tenant,
                    kind="index_version",
                    name=item.filename,
                    parent_id=asset.id,
                    metadata={
                        "operation": "bulk.intake",
                        "bulk_item_id": item_id,
                        "sha256": item.sha256,
                        "bytes": item.size_bytes,
                    },
                )
                await self.catalog.update(subject, tenant, version.id, {"status": "pending"})
                reservation = DatasetReservation(
                    native_dataset_id=uuid4(), native_file_id=uuid4(), catalog_file_version_id=version.id
                ).model_dump(mode="json")
            await self.records.add_item(
                BulkItem(
                    id=item_id,
                    batch_id=row.id,
                    ordinal=ordinal,
                    **item.model_dump(),
                    source_id=source.id,
                    asset_id=asset.id,
                    status="awaiting_upload",
                    reservation_json=reservation,
                )
            )
        quota.reserved_bytes += total
        await self.records.flush()
        return await self._view(row)

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _output_guard(self, subject: str, tenant: str, identifier: str) -> None:
        await self._scope(subject, tenant, identifier)

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _get(self, subject: str, tenant: str, identifier: str) -> FileBatchView:
        return await self._view(await self._scope(subject, tenant, identifier))

    async def get(self, subject: str, tenant: str, identifier: str) -> FileBatchView:
        result = await self._get(subject, tenant, identifier)
        await self._output_guard(subject, tenant, identifier)
        return result

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _list(self, subject: str, tenant: str, page: int, page_size: int) -> FileBatchPage:
        bounds = await self.authority.read_bounds(subject, tenant)
        rows, total = await self.records.visible_page(
            tenant, subject, token_identity(), page, page_size, **bounds
        )
        return FileBatchPage(
            items=[await self._view(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def list(self, subject: str, tenant: str, *, page: int = 1, page_size: int = 25) -> FileBatchPage:
        self._validate_page(page, page_size)
        result = await self._list(subject, tenant, page, page_size)
        current = await self._list(subject, tenant, page, page_size)
        if current != result:
            raise ConflictException("Bulk page changed; request a current page", code="BULK_PAGE_CHANGED")
        await self._list_guard(subject, tenant, current)
        return current

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _list_guard(self, subject: str, tenant: str, result: FileBatchPage) -> None:
        bounds = await self.authority.read_bounds(subject, tenant)
        rows, total = await self.records.visible_page(
            tenant, subject, token_identity(), result.page, result.page_size, **bounds
        )
        if total != result.total or [row.id for row in rows] != [row.id for row in result.items]:
            raise ConflictException("Bulk page authorization changed", code="BULK_PAGE_CHANGED")

    @staticmethod
    def _validate_page(page: int, page_size: int) -> None:
        if (
            type(page) is not int
            or not 1 <= page <= 1000000
            or type(page_size) is not int
            or not 1 <= page_size <= 100
        ):
            raise InvalidRequestException("Use bounded pagination", code="BULK_INVALID_PAGE")

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _items(
        self, subject: str, tenant: str, identifier: str, page: int, page_size: int
    ) -> FileItemPage:
        await self._scope(subject, tenant, identifier)
        rows, total = await self.records.page(identifier, page, page_size)
        return FileItemPage(
            items=[
                FileBatchItemView(
                    id=r.id,
                    client_item_id=r.client_item_id,
                    filename=r.filename,
                    mode=r.mode,
                    size_bytes=r.size_bytes,
                    sha256=r.sha256,
                    status=r.status,
                    source_id=r.source_id,
                    asset_id=r.asset_id,
                    job_id=r.job_id,
                    file_version_id=DatasetReservation.stored(r.reservation_json).catalog_file_version_id
                    if r.mode == "dataset"
                    else None,
                    table_ids=[t["catalog_table_id"] for t in (r.receipt_json or {}).get("tables", [])],
                    source_version_id=(r.receipt_json or {}).get("source_version_id"),
                    extraction_id=(r.receipt_json or {}).get("extraction_id"),
                    error_code=r.error_code,
                )
                for r in rows
            ],
            total=total,
            page=page,
            page_size=page_size,
            pages=(total + page_size - 1) // page_size,
        )

    async def items(
        self, subject: str, tenant: str, identifier: str, *, page: int = 1, page_size: int = 25
    ) -> FileItemPage:
        self._validate_page(page, page_size)
        result = await self._items(subject, tenant, identifier, page, page_size)
        await self._output_guard(subject, tenant, identifier)
        return result

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _begin_upload(
        self, subject: str, tenant: str, batch: str, item_id: str, content: bytes | None, key: str
    ) -> UploadTicket:
        row = await self._scope(subject, tenant, batch, write=True)
        global_quota = await self.records.quota("global:uploads")
        quota = await self.records.quota("tenant:" + tenant)
        item = await self._item_for_write(subject, tenant, row, item_id)
        if item.size_bytes > self.storage.effective_file_limit():
            raise PayloadTooLargeException("Original exceeds the current byte limit", code="BULK_FILE_LIMIT")
        if content is not None and (
            not isinstance(content, bytes)
            or len(content) != item.size_bytes
            or hashlib.sha256(content).hexdigest() != item.sha256
        ):
            raise ConflictException("Bytes differ from admitted manifest", code="BULK_CONTENT_MISMATCH")
        previous = (
            await self.records.upload_by_id(item.winning_upload_id)
            if item.winning_upload_id
            else await self.records.upload(item_id, key_digest(key))
        )
        if previous:
            return UploadTicket(previous.id, previous.object_key, item.size_bytes, item.sha256, False)
        if row.submitted or row.cancelled or row.expires_at <= now():
            raise GoneException("Unsubmitted staging is closed", code="BULK_STAGING_CLOSED")
        if (
            quota.active_uploads >= self.settings.max_uploads_per_tenant
            or global_quota.active_uploads >= self.settings.max_uploads_global
        ):
            raise RateLimitException("Upload concurrency is full", code="BULK_UPLOAD_LIMIT")
        attempts = await self.records.upload_count(item.id)
        if attempts >= self.settings.max_upload_attempts_per_item:
            raise RateLimitException(
                "Retained original attempts reached their bound", code="BULK_UPLOAD_ATTEMPT_LIMIT"
            )
        extra = item.size_bytes if attempts else 0
        if quota.reserved_bytes + extra > self.settings.max_staged_bytes_per_tenant:
            raise RateLimitException("Retained attempts exceed tenant quota", code="BULK_QUOTA_EXCEEDED")
        quota.reserved_bytes += extra
        identifier = str(uuid4())
        owner = secrets.token_hex(32)
        timestamp = await self.records.clock()
        upload = BulkUpload(
            id=identifier,
            item_id=item.id,
            key_hash=key_digest(key),
            object_key=f"bulk/{batch}/{item_id}/{identifier}.blob",
            status="uploading",
            permit_held=True,
        )
        await self.records.add_upload(upload)
        storage_identity = self.storage.identity()
        await self.records.add_upload_state(
            BulkUploadState(
                upload_id=upload.id,
                generation=1,
                owner_hash=digest(owner),
                operation="writing",
                lease_until=timestamp + timedelta(seconds=self.settings.upload_lease_seconds),
                storage_identity=storage_identity,
            )
        )
        quota.active_uploads += 1
        global_quota.active_uploads += 1
        return UploadTicket(
            upload.id,
            upload.object_key,
            item.size_bytes,
            item.sha256,
            True,
            writer_token=owner,
            generation=1,
            storage_identity=storage_identity,
        )

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _finish_upload(
        self, subject: str, tenant: str, batch: str, item_id: str, ticket: UploadTicket, object_reference=None
    ) -> StagedFileReceipt:
        row = await self._scope(subject, tenant, batch, write=True)
        global_quota = await self.records.quota("global:uploads")
        quota = await self.records.quota("tenant:" + tenant)
        item = await self._item_for_write(subject, tenant, row, item_id)
        upload = await self.records.upload_by_id(ticket.upload_id, lock=True)
        if (
            item is None
            or upload is None
            or upload.item_id != item.id
            or upload.object_key != ticket.object_key
            or item.size_bytes != ticket.size_bytes
            or item.sha256 != ticket.sha256
        ):
            raise ConflictException("Upload identity changed", code="BULK_UPLOAD_CONFLICT")
        state = await self.records.upload_state(upload.id, lock=True)
        self._require_writer(state, ticket, await self.records.clock())
        if object_reference is not None:
            if (object_reference.key, object_reference.size_bytes, object_reference.sha256) != (
                upload.object_key,
                item.size_bytes,
                item.sha256,
            ):
                raise ConflictException(
                    "Pinned original differs from manifest", code="BULK_ORIGINAL_INTEGRITY"
                )
            upload.object_reference_json = object_reference.to_dict()
        if upload.permit_held:
            global_quota.active_uploads -= 1
            quota.active_uploads -= 1
            upload.permit_held = False
        if (row.cancelled or row.submitted or row.expires_at <= now()) and (
            item.winning_upload_id != upload.id or upload.status != "verified"
        ):
            raise ConflictException("Staging changed while bytes were written", code="BULK_STAGING_CLOSED")
        if item.winning_upload_id is None:
            item.winning_upload_id = upload.id
            item.status = "staged"
            upload.status = "verified"
            row.revision += 1
        state.operation = "closed"
        winner = await self.records.upload_by_id(item.winning_upload_id)
        if winner is None or winner.status != "verified":
            raise ConflictException("Original receipt is unresolved", code="BULK_UPLOAD_PENDING")
        await self.records.flush()
        return StagedFileReceipt(
            receipt_id=winner.id,
            batch_id=batch,
            item_id=item.id,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
        )

    @staticmethod
    def _require_writer(state: BulkUploadState | None, ticket: UploadTicket, timestamp) -> None:
        if (
            not ticket.write
            or state is None
            or state.operation != "writing"
            or state.generation != ticket.generation
            or state.owner_hash != digest(ticket.writer_token)
            or state.lease_until <= timestamp
            or state.storage_identity != ticket.storage_identity
        ):
            raise ConflictException("Upload writer lease was lost", code="BULK_UPLOAD_LEASE_LOST")

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _writer_check(
        self, subject: str, tenant: str, batch: str, item_id: str, ticket: UploadTicket
    ) -> None:
        row = await self._scope(subject, tenant, batch, write=True)
        item = await self._item_for_write(subject, tenant, row, item_id)
        upload = await self.records.upload_by_id(ticket.upload_id, lock=True)
        if (
            upload is None
            or upload.item_id != item.id
            or upload.object_key != ticket.object_key
            or ticket.size_bytes != item.size_bytes
            or ticket.sha256 != item.sha256
        ):
            raise ConflictException("Upload identity changed", code="BULK_UPLOAD_CONFLICT")
        self._require_writer(
            await self.records.upload_state(ticket.upload_id, lock=True), ticket, await self.records.clock()
        )
        if row.cancelled or row.submitted or row.expires_at <= await self.records.clock():
            raise ConflictException("Staging is closed", code="BULK_STAGING_CLOSED")
        if self.storage.identity() != ticket.storage_identity:
            raise ConflictException("Bulk storage profile changed", code="BULK_STORAGE_CHANGED")

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _uncertain(self, tenant: str, ticket: UploadTicket) -> None:
        await self.records.authority_lock(tenant, "", None)
        global_quota = await self.records.quota("global:uploads")
        quota = await self.records.quota("tenant:" + tenant)
        upload = await self.records.tenant_upload(tenant, ticket.upload_id, lock=True)
        state = await self.records.upload_state(ticket.upload_id, lock=True)
        if (
            upload is None
            or state is None
            or state.operation != "writing"
            or state.generation != ticket.generation
            or state.owner_hash != digest(ticket.writer_token)
        ):
            return
        if upload.permit_held:
            global_quota.active_uploads -= 1
            quota.active_uploads -= 1
            upload.permit_held = False
        state.operation = "closed"
        state.generation += 1
        if upload.status == "uploading":
            upload.status = "uncertain"
        await self.records.flush()

    @transactional(
        datasource="primary", propagation=Propagation.REQUIRES_NEW, read_only=True, read_from_primary=True
    )
    async def _expired_staging(self) -> Sequence[tuple[str, str, int]]:
        return await self.records.expired_staging()

    @transactional(datasource="primary", propagation=Propagation.REQUIRES_NEW, read_from_primary=True)
    async def _expire_staging(self, tenant: str, upload_id: str, generation: int) -> None:
        await self.records.authority_lock(tenant, "", None)
        global_uploads = await self.records.quota("global:uploads")
        tenant_uploads = await self.records.quota("tenant:" + tenant)
        global_io = await self.records.quota("global:recoveries")
        tenant_io = await self.records.quota("recovery:tenant:" + tenant)
        upload = await self.records.tenant_upload(tenant, upload_id, lock=True)
        state = await self.records.upload_state(upload_id, lock=True)
        if (
            upload is None
            or state is None
            or state.generation != generation
            or state.operation not in {"writing", "verifying"}
            or state.lease_until > await self.records.clock()
        ):
            return
        if state.operation == "writing" and upload.permit_held:
            global_uploads.active_uploads -= 1
            tenant_uploads.active_uploads -= 1
            upload.permit_held = False
            if upload.status == "uploading":
                upload.status = "uncertain"
        if state.operation == "verifying":
            action = await self.records.recovery_by_id(state.recovery_id) if state.recovery_id else None
            if (
                action is None
                or action.upload_id != upload.id
                or action.generation != generation
                or action.owner_hash != state.owner_hash
                or action.completed
            ):
                raise ConflictException("Recovery journal binding changed", code="BULK_RECOVERY_JOURNAL")
            if action.permit_held:
                global_io.active_uploads -= 1
                tenant_io.active_uploads -= 1
                action.permit_held = False
        state.operation = "closed"
        state.generation += 1
        await self.records.flush()

    async def _expire_staging_capacity(self) -> None:
        for tenant, upload_id, generation in await self._expired_staging():
            await self._expire_staging(tenant, upload_id, generation)

    async def _reserve_upload(
        self, subject: str, tenant: str, batch: str, item_id: str, content: bytes | None, key: str
    ) -> UploadTicket:
        permit = self.storage.writer_permit()
        try:
            try:
                ticket = await self._begin_upload(subject, tenant, batch, item_id, content, key)
            except RateLimitException as error:
                if error.code != "BULK_UPLOAD_LIMIT":
                    raise
                await self._expire_staging_capacity()
                ticket = await self._begin_upload(subject, tenant, batch, item_id, content, key)
            if ticket.write:
                return replace(ticket, local_permit=permit)
            permit.close()
            return ticket
        except BaseException:
            permit.close()
            raise

    async def reserve_stream(
        self, subject: str, tenant: str, batch: str, item_id: str, key: str
    ) -> UploadTicket:
        if current_unit_of_work("primary") is not None:
            raise ConflictException(
                "Blob staging requires independently committed units", code="BULK_AMBIENT_TRANSACTION"
            )
        self.settings.validate()
        key_digest(key)
        return await self._reserve_upload(subject, tenant, batch, item_id, None, key)

    async def abort_stream(self, tenant: str, ticket: UploadTicket) -> None:
        try:
            if ticket.write:
                await self._uncertain(tenant, ticket)
        finally:
            if ticket.local_permit:
                ticket.local_permit.close()

    async def finish_stream(
        self,
        subject: str,
        tenant: str,
        batch: str,
        item_id: str,
        ticket: UploadTicket,
        content: bytes | Path | None,
        received_bytes: int,
        received_sha256: str,
    ) -> StagedFileReceipt:
        if current_unit_of_work("primary") is not None:
            raise ConflictException(
                "Blob staging requires independently committed units", code="BULK_AMBIENT_TRANSACTION"
            )
        task = None
        try:
            if received_bytes != ticket.size_bytes or received_sha256 != ticket.sha256:
                raise ConflictException("Bytes differ from admitted manifest", code="BULK_CONTENT_MISMATCH")
            reference = None
            if ticket.write:
                if isinstance(content, Path):
                    with source_file(content, self.settings.max_file_bytes) as (_, size, actual_digest):
                        if (size, actual_digest) != (ticket.size_bytes, ticket.sha256):
                            raise ConflictException(
                                "Original differs from manifest", code="BULK_CONTENT_MISMATCH"
                            )

                    def operation():
                        return self.storage.put_file(ticket.object_key, content, ticket.sha256)
                elif (
                    isinstance(content, bytes)
                    and len(content) == ticket.size_bytes
                    and hashlib.sha256(content).hexdigest() == ticket.sha256
                ):

                    def operation():
                        return self.storage.put(ticket.object_key, content, ticket.sha256)
                else:
                    raise ConflictException(
                        "Original differs from stream receipt", code="BULK_CONTENT_MISMATCH"
                    )
                await self._writer_check(subject, tenant, batch, item_id, ticket)
                task = asyncio.create_task(operation())
                reference = await asyncio.shield(task)
            else:
                return await self.receipt(subject, tenant, batch, item_id)
            return await self._finish_upload(
                subject, tenant, batch, item_id, ticket, object_reference=reference
            )
        except BaseException:
            if task is not None:
                while not task.done():
                    try:
                        await asyncio.shield(task)
                    except asyncio.CancelledError:
                        continue
                    except Exception:
                        break
                with suppress(BaseException):
                    task.result()
            await self.abort_stream(tenant, ticket)
            raise
        finally:
            if ticket.local_permit:
                ticket.local_permit.close()

    async def stage(
        self, subject: str, tenant: str, batch: str, item_id: str, content: bytes, key: str
    ) -> StagedFileReceipt:
        if current_unit_of_work("primary") is not None:
            raise ConflictException(
                "Blob staging requires independently committed units", code="BULK_AMBIENT_TRANSACTION"
            )
        key_digest(key)
        ticket = await self._reserve_upload(subject, tenant, batch, item_id, content, key)
        return await self.finish_stream(
            subject,
            tenant,
            batch,
            item_id,
            ticket,
            content,
            len(content),
            hashlib.sha256(content).hexdigest(),
        )

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _recovery_ticket(
        self, subject: str, tenant: str, batch: str, item_id: str, body: BulkAction, key: str
    ) -> RecoveryTicket | None:
        row = await self._scope(subject, tenant, batch, write=True)
        request_hash = digest(["recover:" + item_id, body.model_dump(), token_identity()])
        key_hash = key_digest(key)
        recorded = row.actions_json.get(key_hash)
        pending_marker = "pending-recovery:" + request_hash
        if recorded and recorded != pending_marker:
            if recorded != request_hash:
                raise ConflictException("Recovery key differs", code="IDEMPOTENCY_CONFLICT")
            return None
        global_uploads = await self.records.quota("global:uploads")
        tenant_uploads = await self.records.quota("tenant:" + tenant)
        global_io = await self.records.quota("global:recoveries")
        tenant_io = await self.records.quota("recovery:tenant:" + tenant)
        item = await self._item_for_write(subject, tenant, row, item_id)
        action = await self.records.recovery(batch, key_hash)
        if recorded == pending_marker and action is None:
            raise ConflictException("Pending recovery journal is unavailable", code="BULK_RECOVERY_JOURNAL")
        if action and action.request_hash != request_hash:
            raise ConflictException("Recovery key differs", code="IDEMPOTENCY_CONFLICT")
        upload = (
            await self.records.upload_by_id(action.upload_id, lock=True)
            if action
            else await self.records.latest_upload(item.id)
        )
        if upload is None or upload.item_id != item.id:
            raise ConflictException("No retained original", code="BULK_UPLOAD_PENDING")
        state = await self.records.upload_state(upload.id, lock=True)
        timestamp = await self.records.clock()
        if state is None:
            raise ConflictException("Legacy writer requires reviewed cutover", code="BULK_LEGACY_WRITER")
        if state.storage_identity != self.storage.identity():
            raise ConflictException("Bulk storage profile changed", code="BULK_STORAGE_CHANGED")
        if state.operation in {"writing", "verifying"} and state.lease_until > timestamp:
            raise ConflictException("Original operation is still active", code="BULK_UPLOAD_ACTIVE")
        if action is None:
            if body.expected_revision != row.revision:
                raise ConflictException("Batch revision changed", code="BULK_REVISION_CONFLICT")
            if len(row.actions_json) >= 256:
                raise RateLimitException("Action history is full", code="BULK_ACTION_LIMIT")
        elif action.fenced_revision != row.revision:
            raise ConflictException("Batch changed during recovery", code="BULK_REVISION_CONFLICT")
        previous_action = await self.records.recovery_by_id(state.recovery_id) if state.recovery_id else None
        if previous_action and previous_action.permit_held:
            if (
                previous_action.upload_id != upload.id
                or previous_action.batch_id != batch
                or previous_action.generation != state.generation
                or previous_action.owner_hash != state.owner_hash
                or previous_action.completed
            ):
                raise ConflictException("Recovery journal binding changed", code="BULK_RECOVERY_JOURNAL")
            global_io.active_uploads -= 1
            tenant_io.active_uploads -= 1
            previous_action.permit_held = False
        if (
            global_io.active_uploads >= self.settings.max_recoveries_global
            or tenant_io.active_uploads >= self.settings.max_recoveries_per_tenant
        ):
            raise RateLimitException("Recovery I/O is full", code="BULK_RECOVERY_LIMIT")
        if upload.permit_held:
            global_uploads.active_uploads -= 1
            tenant_uploads.active_uploads -= 1
            upload.permit_held = False
        if upload.status == "uploading":
            upload.status = "uncertain"
        state.generation += 1
        owner = secrets.token_hex(32)
        state.owner_hash, state.operation = digest(owner), "verifying"
        state.lease_until = timestamp + timedelta(seconds=self.settings.recovery_lease_seconds)
        if action is None:
            row.revision += 1
            row.actions_json = {**row.actions_json, key_hash: pending_marker}
            action = BulkRecovery(
                id=str(uuid4()),
                batch_id=batch,
                upload_id=upload.id,
                key_hash=key_hash,
                request_hash=request_hash,
                fenced_revision=row.revision,
                generation=state.generation,
                owner_hash=state.owner_hash,
                lease_until=state.lease_until,
                permit_held=True,
                completed=False,
            )
            state.recovery_id = action.id
            await self.records.add_recovery(action)
        else:
            action.generation, action.owner_hash = state.generation, state.owner_hash
            action.lease_until, action.permit_held = state.lease_until, True
        state.recovery_id = action.id
        global_io.active_uploads += 1
        tenant_io.active_uploads += 1
        await self.records.flush()
        ticket = UploadTicket(
            upload.id,
            upload.object_key,
            item.size_bytes,
            item.sha256,
            False,
            storage_identity=state.storage_identity,
        )
        return RecoveryTicket(ticket, action.id, owner, state.generation, action.fenced_revision)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _recover_original(
        self,
        subject: str,
        tenant: str,
        batch: str,
        item_id: str,
        body: BulkAction,
        key: str,
        ticket: RecoveryTicket,
        verified: bool,
        object_reference=None,
    ) -> FileBatchView:
        row = await self._scope(subject, tenant, batch, write=True)
        global_io = await self.records.quota("global:recoveries")
        tenant_io = await self.records.quota("recovery:tenant:" + tenant)
        item = await self._item_for_write(subject, tenant, row, item_id)
        upload = await self.records.tenant_upload(tenant, ticket.upload.upload_id, lock=True)
        state = await self.records.upload_state(ticket.upload.upload_id, lock=True)
        action = await self.records.recovery_by_id(ticket.action_id)
        timestamp = await self.records.clock()
        if (
            state is None
            or action is None
            or upload is None
            or upload.item_id != item.id
            or state.operation != "verifying"
            or state.recovery_id != action.id
            or state.generation != ticket.generation
            or state.owner_hash != digest(ticket.token)
            or state.lease_until <= timestamp
            or action.generation != ticket.generation
            or action.owner_hash != state.owner_hash
            or action.completed
            or not action.permit_held
            or action.batch_id != batch
            or action.upload_id != upload.id
            or action.key_hash != key_digest(key)
            or action.request_hash != digest(["recover:" + item_id, body.model_dump(), token_identity()])
            or upload.object_key != ticket.upload.object_key
            or item.sha256 != ticket.upload.sha256
            or item.size_bytes != ticket.upload.size_bytes
        ):
            raise ConflictException("Recovery lease was lost", code="BULK_UPLOAD_LEASE_LOST")
        if row.revision != ticket.fenced_revision:
            raise ConflictException("Batch changed during verification", code="BULK_REVISION_CONFLICT")
        if state.storage_identity != self.storage.identity():
            raise ConflictException("Bulk storage profile changed", code="BULK_STORAGE_CHANGED")
        if (
            verified
            and not row.submitted
            and not row.cancelled
            and row.expires_at > timestamp
            and item.winning_upload_id is None
        ):
            item.winning_upload_id, item.status, upload.status = upload.id, "staged", "verified"
            if object_reference is not None:
                upload.object_reference_json = object_reference.to_dict()
        state.operation = "closed"
        global_io.active_uploads -= 1
        tenant_io.active_uploads -= 1
        action.permit_held, action.completed = False, True
        row.actions_json = {**row.actions_json, key_digest(key): action.request_hash}
        row.revision += 1
        await self.records.flush()
        return await self._view(row)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def _abort_recovery(self, tenant: str, ticket: RecoveryTicket) -> None:
        await self.records.authority_lock(tenant, "", None)
        global_io = await self.records.quota("global:recoveries")
        tenant_io = await self.records.quota("recovery:tenant:" + tenant)
        upload = await self.records.tenant_upload(tenant, ticket.upload.upload_id)
        if upload is None:
            return
        state = await self.records.upload_state(upload.id, lock=True)
        action = await self.records.recovery_by_id(ticket.action_id)
        if (
            state is not None
            and action is not None
            and state.operation == "verifying"
            and state.generation == ticket.generation
            and state.owner_hash == digest(ticket.token)
            and state.recovery_id == action.id
            and action.upload_id == upload.id
            and action.generation == ticket.generation
            and action.owner_hash == state.owner_hash
            and not action.completed
            and action.permit_held
        ):
            global_io.active_uploads -= 1
            tenant_io.active_uploads -= 1
            action.permit_held = False
            state.operation = "closed"
            state.lease_until = await self.records.clock()
            await self.records.flush()

    async def recover_original(
        self, subject: str, tenant: str, batch: str, item_id: str, body: BulkAction, key: str
    ) -> FileBatchView:
        if current_unit_of_work("primary") is not None:
            raise ConflictException(
                "Blob staging requires independently committed units", code="BULK_AMBIENT_TRANSACTION"
            )
        try:
            ticket = await self._recovery_ticket(subject, tenant, batch, item_id, body, key)
        except RateLimitException as error:
            if error.code != "BULK_RECOVERY_LIMIT":
                raise
            await self._expire_staging_capacity()
            ticket = await self._recovery_ticket(subject, tenant, batch, item_id, body, key)
        if ticket is None:
            return await self.get(subject, tenant, batch)
        try:
            reference = None
            try:
                if ticket.upload.size_bytes > 32 * 1024**2:
                    reference = await self.storage.verify_file(
                        ticket.upload.object_key,
                        ticket.upload.size_bytes,
                        ticket.upload.sha256,
                        storage_identity=ticket.upload.storage_identity,
                    )
                else:
                    await self.storage.read(
                        ticket.upload.object_key,
                        ticket.upload.size_bytes,
                        ticket.upload.sha256,
                        storage_identity=ticket.upload.storage_identity,
                    )
                verified = True
            except FileNotFoundError:
                verified = False
            return await self._recover_original(
                subject, tenant, batch, item_id, body, key, ticket, verified, object_reference=reference
            )
        except BaseException:
            await self._abort_recovery(tenant, ticket)
            raise

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    )
    async def _receipt(
        self, subject: str, tenant: str, batch: str, item_id: str
    ) -> tuple[StagedFileReceipt, BulkUpload]:
        await self._scope(subject, tenant, batch)
        item = await self.records.item(batch, item_id)
        upload = (
            await self.records.upload_by_id(item.winning_upload_id)
            if item and item.winning_upload_id
            else None
        )
        if item is None or upload is None or upload.status != "verified":
            raise ConflictException("Original has no verified receipt", code="BULK_UPLOAD_PENDING")
        state = await self.records.upload_state(upload.id)
        if state is None and self.settings.storage_backend != "local":
            raise ConflictException("Legacy original requires reviewed transfer", code="BULK_STORAGE_CHANGED")
        if state is not None and state.storage_identity != self.storage.identity():
            raise ConflictException("Retained staging profile differs", code="BULK_STORAGE_CHANGED")
        return StagedFileReceipt(
            receipt_id=upload.id,
            batch_id=batch,
            item_id=item.id,
            sha256=item.sha256,
            size_bytes=item.size_bytes,
        ), upload

    async def receipt(self, subject: str, tenant: str, batch: str, item_id: str) -> StagedFileReceipt:
        result, upload = await self._receipt(subject, tenant, batch, item_id)
        if upload.object_reference_json is not None:
            import tempfile

            from koinon.knowledge.bulk.queue import BulkOriginal

            with tempfile.TemporaryDirectory(prefix="koinon-receipt-") as directory:
                await self.storage.read_file(
                    BulkOriginal(
                        upload.object_key,
                        result.size_bytes,
                        result.sha256,
                        self.storage.identity(),
                        upload.object_reference_json,
                    ),
                    Path(directory) / "original",
                )
        else:
            await self.storage.read(
                upload.object_key, result.size_bytes, result.sha256, storage_identity=self.storage.identity()
            )
        await self._output_guard(subject, tenant, batch)
        return result

    def _action(self, row: BulkBatch, action: str, key: str, body: BulkAction) -> bool:
        key_hash = key_digest(key)
        expected = digest([action, body.model_dump(), token_identity()])
        previous = row.actions_json.get(key_hash)
        if previous:
            if previous != expected:
                raise ConflictException(
                    "Action key belongs to a different request", code="IDEMPOTENCY_CONFLICT"
                )
            return False
        if body.expected_revision != row.revision:
            raise ConflictException("Batch revision changed", code="BULK_REVISION_CONFLICT")
        if len(row.actions_json) >= 256:
            raise RateLimitException("Batch action receipt limit reached", code="BULK_ACTION_LIMIT")
        row.actions_json = {**row.actions_json, key_hash: expected}
        return True

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def submit(
        self, subject: str, tenant: str, identifier: str, body: BulkAction, key: str
    ) -> FileBatchView:
        row = await self._scope(subject, tenant, identifier, write=True)
        if not self._action(row, "submit", key, body):
            return await self._view(row)
        items = await self.records.all_items(row.id)
        if (
            row.cancelled
            or row.submitted
            or row.expires_at <= now()
            or any(item.status != "staged" for item in items)
        ):
            raise ConflictException(
                "Every original must be staged before one submission", code="BULK_NOT_STAGED"
            )
        for item in items:
            await self._item_for_write(subject, tenant, row, item.id)
            item.connection_json = await self.records.connection(tenant, row.workspace_id, item.mode)
            job = await self.jobs.submit(
                tenant,
                item.asset_id,
                "knowledge.bulk.intake",
                {"batch_id": row.id, "item_id": item.id},
                "bulk:" + item.id,
            )
            item.job_id = job.id
            item.status = "queued"
        row.submitted = True
        row.revision += 1
        await self.records.flush()
        return await self._view(row)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def cancel(
        self, subject: str, tenant: str, identifier: str, body: BulkAction, key: str
    ) -> FileBatchView:
        row = await self._scope(subject, tenant, identifier, write=True)
        if not self._action(row, "cancel", key, body):
            return await self._view(row)
        row.cancelled = True
        for item in await self.records.all_items(row.id):
            if item.status in {"succeeded", "failed", "cancelled"}:
                continue
            job = await self.records.job(item.job_id) if item.job_id else None
            if item.native_workspace_id and job is not None:
                port = self.intakes.get() if self.intakes else None
                try:
                    if port is None:
                        raise ConflictException(
                            "Native receipt lookup unavailable", code="BULK_NATIVE_REQUIRED"
                        )
                    lease = BulkQueue._lease(job, item, row)
                    observed = await port.inspect(lease)
                except Exception:
                    item.status = "reconciling"
                    item.error_code = "BULK_CANCELLATION_UNKNOWN"
                    if job.status in {"running", "queued"}:
                        await self.jobs.cancel(tenant, job.id)
                    continue
                if observed.status == "committed" and observed.receipt is not None:
                    await port.acknowledge_committed(lease, observed.receipt)
                    continue
            item.status = "cancelled"
            if job is not None and job.status in {"queued", "running"}:
                await self.jobs.cancel(tenant, job.id)
        row.revision += 1
        await self.records.flush()
        return await self._view(row)

    @transactional(propagation=Propagation.REQUIRES_NEW)
    async def reconcile(
        self, subject: str, tenant: str, identifier: str, item_id: str, body: BulkAction, key: str
    ) -> FileBatchView:
        row = await self._scope(subject, tenant, identifier, write=True)
        if not self._action(row, "reconcile:" + item_id, key, body):
            return await self._view(row)
        item = await self.records.item(row.id, item_id, lock=True)
        if item is None:
            raise AccessDenied("Intake item is unavailable", code="ACCESS_DENIED")
        if item.status == "succeeded":
            return await self._view(row)
        job = await self.records.job(item.job_id) if item.job_id else None
        port = self.intakes.get() if self.intakes else None
        if not item.native_workspace_id or job is None or port is None:
            raise ConflictException(
                "No native operation is available for receipt reconciliation",
                code="BULK_NATIVE_RECEIPT_REQUIRED",
            )
        lease = BulkQueue._lease(job, item, row)
        observed = await port.inspect(lease)
        if observed.status == "committed" and observed.receipt is not None:
            await port.acknowledge_committed(lease, observed.receipt)
        elif row.cancelled:
            item.status = "cancelled"
            item.error_code = None
        else:
            item.status = "reconciling"
            item.error_code = "BULK_NATIVE_OUTCOME_UNRESOLVED"
        row.revision += 1
        await self.records.flush()
        return await self._view(row)

    async def _processing_recovery(self, row: BulkBatch, item: BulkItem):
        job = await self.records.job(item.job_id) if item.job_id else None
        if job is None:
            raise ConflictException("Processing job is unavailable", code="BULK_NATIVE_RECEIPT_REQUIRED")
        if (
            job.tenant_id != row.tenant_id
            or job.resource_id != item.asset_id
            or job.payload != {"batch_id": row.id, "item_id": item.id}
            or job.idempotency_key != "bulk:" + item.id
            or not 0 <= job.attempts <= job.max_attempts <= 2147483647
            or job.max_attempts < 1
        ):
            raise ConflictException("Processing reservation changed", code="BULK_NATIVE_RECEIPT_CONFLICT")

        upload = await self.records.upload_by_id(item.winning_upload_id) if item.winning_upload_id else None
        verified_original = (
            upload is not None
            and upload.item_id == item.id
            and upload.status == "verified"
            and not upload.permit_held
        )

        def descriptor(
            state: NativeRecoveryState = "not_checked",
            operation: RecoveryOperation | None = None,
            reason=None,
            checked=None,
        ) -> FileRecoveryView:
            return FileRecoveryView(
                batch_id=row.id,
                item_id=item.id,
                batch_revision=row.revision,
                native_state=state,
                operation=operation,
                reason_code=reason,
                attempts=job.attempts,
                max_attempts=job.max_attempts,
                checked_at=checked,
                job_status=job.status
                if job.status in {"queued", "running", "succeeded", "failed", "cancelled"}
                else "unknown",
                original_receipt_state="verified" if verified_original else "unavailable",
            )

        if row.cancelled or row.expires_at <= now() or not row.submitted:
            return descriptor(reason="BULK_RECOVERY_UNAVAILABLE"), job, None, None
        if item.status not in {"reconciling", "failed"}:
            return descriptor(reason="BULK_RECOVERY_NOT_REQUIRED"), job, None, None
        # Expired running leases are still unknown, not proof that an old writer drained.
        if job.status != "failed" or job.worker_id is not None or job.lease_until is not None:
            return descriptor(reason="BULK_RECOVERY_BUSY"), job, None, None
        if not item.native_workspace_id:
            return descriptor(reason="BULK_NATIVE_RECEIPT_REQUIRED"), job, None, None
        if item.connection_json != await self.records.connection(row.tenant_id, row.workspace_id, item.mode):
            return descriptor(reason="BULK_CONNECTION_CHANGED"), job, None, None
        if not await self.records.workspace_matches(
            row.tenant_id,
            row.workspace_id,
            "canon" if item.mode == "document" else "structured",
            item.native_workspace_id,
        ):
            return descriptor(reason="BULK_NATIVE_SCOPE_CHANGED"), job, None, None
        port = self.intakes.get() if self.intakes else None
        if port is None:
            return descriptor(reason="BULK_NATIVE_REQUIRED"), job, None, None
        lease = BulkQueue._lease(job, item, row)
        with SecurityContextHolder.using(execution_context(row.subject, row.token_id)):
            try:
                async with asyncio.timeout(10):
                    observed = await port.inspect(lease)
            except ForbiddenException:
                raise
            except Exception:
                return (
                    descriptor("unknown", reason="BULK_NATIVE_OUTCOME_UNRESOLVED", checked=now()),
                    job,
                    lease,
                    port,
                )
        checked = now()
        if observed.status == "committed":
            receipt = observed.receipt
            if (
                receipt is None
                or receipt.sha256 != item.sha256
                or receipt.size_bytes != item.size_bytes
                or receipt.native_workspace_id != item.native_workspace_id
                or receipt.domain != ("canon" if item.mode == "document" else "structured")
                or (item.native_id is not None and item.native_id != receipt.native_asset_id)
            ):
                return (
                    descriptor("committed", reason="BULK_NATIVE_RECEIPT_CONFLICT", checked=checked),
                    job,
                    lease,
                    port,
                )
            return descriptor("committed", "acknowledge_commit", checked=checked), job, lease, port
        if observed.status not in {"absent", "prepared"}:
            return (
                descriptor(observed.status, reason="BULK_NATIVE_OUTCOME_UNRESOLVED", checked=checked),
                job,
                lease,
                port,
            )
        if observed.receipt is not None or item.native_id is not None or item.receipt_json is not None:
            return (
                descriptor(observed.status, reason="BULK_NATIVE_RECEIPT_CONFLICT", checked=checked),
                job,
                lease,
                port,
            )
        if job.attempts >= job.max_attempts:
            return (
                descriptor(observed.status, reason="BULK_RETRY_EXHAUSTED", checked=checked),
                job,
                lease,
                port,
            )
        if observed.status == "prepared":
            if item.mode != "dataset":
                return (
                    descriptor("prepared", reason="BULK_NATIVE_RECEIPT_CONFLICT", checked=checked),
                    job,
                    lease,
                    port,
                )
            return descriptor("prepared", "finalize_publication", checked=checked), job, lease, port
        if not verified_original:
            return descriptor("absent", reason="BULK_ORIGINAL_UNAVAILABLE", checked=checked), job, lease, port
        return descriptor("absent", "retry_processing", checked=checked), job, lease, port

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_from_primary=True,
    )
    async def processing_recovery(
        self, subject: str, tenant: str, identifier: str, item_id: str
    ) -> FileRecoveryView:
        row = await self._scope(subject, tenant, identifier, write=True)
        item = await self._item_for_write(subject, tenant, row, item_id)
        descriptor, _, _, _ = await self._processing_recovery(row, item)
        return descriptor

    @transactional(
        datasource="primary",
        name=PRIMARY_POLICY_UNIT,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_from_primary=True,
    )
    async def recover_processing(
        self, subject: str, tenant: str, identifier: str, item_id: str, body: BulkRecoveryAction, key: str
    ) -> FileBatchView:
        row = await self._scope(subject, tenant, identifier, write=True)
        item = await self._item_for_write(subject, tenant, row, item_id)
        if not self._action(row, "recover_processing:" + item_id, key, body):
            return await self._view(row)
        descriptor, job, lease, port = await self._processing_recovery(row, item)
        if (
            descriptor.operation is None
            or descriptor.operation != body.operation
            or lease is None
            or port is None
        ):
            raise ConflictException(
                "Inspect the current native outcome before choosing a recovery action",
                code=descriptor.reason_code or "BULK_RECOVERY_STATE_CHANGED",
            )
        await self.catalog._audit(
            subject,
            tenant,
            "knowledge.bulk.recovery_requested",
            item.asset_id,
            {
                "batch_id": row.id,
                "item_id": item.id,
                "job_id": job.id,
                "operation": body.operation,
                "native_state": descriptor.native_state,
                "previous_error_code": item.error_code,
                "attempts": job.attempts,
                "max_attempts": job.max_attempts,
            },
        )
        if body.operation == "acknowledge_commit":
            # The native adapter independently rereads the exact commit before primary publication.
            with SecurityContextHolder.using(execution_context(row.subject, row.token_id)):
                observed = await port.inspect(lease)
                if observed.status != "committed" or observed.receipt is None:
                    raise ConflictException("Native outcome changed", code="BULK_RECOVERY_STATE_CHANGED")
                await port.acknowledge_committed(lease, observed.receipt)
        else:
            intent = ProcessingRecoveryIntent(
                operation=body.operation,
                starting_attempt=job.attempts + 1,
                expected_revision=body.expected_revision,
                key_hash=key_digest(key),
                request_hash=row.actions_json[key_digest(key)],
            )
            job.result = {**(job.result or {}), "bulk_processing_recovery": intent.model_dump()}
            job.status, job.available_at, job.updated_at = "queued", now(), now()
            job.error = PENDING_RECOVERY
            item.status, item.error_code = "queued", None
            row.revision += 1
            await self.records.flush()
        return await self._view(row)
