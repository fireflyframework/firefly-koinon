# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, BigInteger, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class BulkBatch(Base):
    __tablename__ = "koinon_bulk_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key_hash", name="uq_bulk_batch_key"),
        Index("ix_bulk_owner_page", "tenant_id", "subject", "created_at", "id"),
        CheckConstraint(
            "revision BETWEEN 1 AND 2147483647 AND total_bytes BETWEEN 1 AND 268435456",
            name="ck_bulk_batch_bounds",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"))
    project_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"))
    parent_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    request_json: Mapped[dict] = mapped_column(JSON)
    actions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(default=1)
    submitted: Mapped[bool] = mapped_column(default=False)
    cancelled: Mapped[bool] = mapped_column(default=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())


class BulkItem(Base):
    __tablename__ = "koinon_bulk_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "client_item_id", name="uq_bulk_item_client"),
        UniqueConstraint("batch_id", "ordinal", name="uq_bulk_item_order"),
        Index("ix_bulk_item_page", "batch_id", "ordinal", "id"),
        CheckConstraint(
            "status IN ('awaiting_upload','staged','queued','running',"
            "'succeeded','failed','cancelled','reconciling')",
            name="ck_bulk_item_status",
        ),
        CheckConstraint(
            "mode IN ('document','dataset') AND ordinal BETWEEN 0 AND 99 "
            "AND size_bytes BETWEEN 1 AND 33554432",
            name="ck_bulk_item_bounds",
        ),
        CheckConstraint(
            "status != 'succeeded' OR (receipt_json IS NOT NULL AND native_id IS NOT NULL "
            "AND native_workspace_id IS NOT NULL)",
            name="ck_bulk_success_receipt",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_bulk_batches.id"))
    ordinal: Mapped[int] = mapped_column()
    client_item_id: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    mode: Mapped[str] = mapped_column(String(16))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"), unique=True)
    asset_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"), unique=True)
    native_workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    native_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("lattice_jobs.id"), nullable=True, unique=True
    )
    status: Mapped[str] = mapped_column(String(24), default="awaiting_upload")
    winning_upload_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connection_json: Mapped[dict] = mapped_column(JSON, default=dict)
    reservation_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)


class BulkUpload(Base):
    __tablename__ = "koinon_bulk_uploads"
    __table_args__ = (
        UniqueConstraint("item_id", "key_hash", name="uq_bulk_upload_key"),
        CheckConstraint("status IN ('uploading','verified','uncertain')", name="ck_bulk_upload_status"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_bulk_items.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    object_key: Mapped[str] = mapped_column(String(1024), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="uploading")
    permit_held: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class BulkTableReservation(Base):
    __tablename__ = "koinon_bulk_table_reservations"
    __table_args__ = (CheckConstraint("ordinal BETWEEN 0 AND 15", name="ck_bulk_table_ordinal"),)
    item_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_bulk_items.id"), primary_key=True)
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    table_id: Mapped[str] = mapped_column(String(64), unique=True)
    snapshot_id: Mapped[str] = mapped_column(String(64), unique=True)
    catalog_table_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"), unique=True)
    name: Mapped[str] = mapped_column(String(255))


class BulkQuota(Base):
    __tablename__ = "koinon_bulk_quotas"
    __table_args__ = (
        CheckConstraint("reserved_bytes >= 0 AND active_uploads >= 0", name="ck_bulk_quota_nonnegative"),
    )
    id: Mapped[str] = mapped_column(String(96), primary_key=True)
    reserved_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    active_uploads: Mapped[int] = mapped_column(default=0)


class BulkUploadState(Base):
    __tablename__ = "koinon_bulk_upload_states"
    __table_args__ = (
        Index("ix_bulk_writer_expiry", "operation", "lease_until", "upload_id"),
        CheckConstraint("generation BETWEEN 1 AND 2147483647", name="ck_bulk_writer_generation"),
        CheckConstraint("operation IN ('writing','verifying','closed')", name="ck_bulk_writer_operation"),
    )
    upload_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_bulk_uploads.id"), primary_key=True)
    generation: Mapped[int] = mapped_column(default=1)
    owner_hash: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(16))
    lease_until: Mapped[datetime] = mapped_column(UtcDateTime())
    storage_identity: Mapped[str] = mapped_column(String(64))
    recovery_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class BulkRecovery(Base):
    __tablename__ = "koinon_bulk_recoveries"
    __table_args__ = (
        UniqueConstraint("batch_id", "key_hash", name="uq_bulk_recovery_key"),
        CheckConstraint("generation BETWEEN 1 AND 2147483647", name="ck_bulk_recovery_generation"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_bulk_batches.id"))
    upload_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_bulk_uploads.id"))
    key_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    fenced_revision: Mapped[int] = mapped_column()
    generation: Mapped[int] = mapped_column()
    owner_hash: Mapped[str] = mapped_column(String(64))
    lease_until: Mapped[datetime] = mapped_column(UtcDateTime())
    permit_held: Mapped[bool] = mapped_column(default=True)
    completed: Mapped[bool] = mapped_column(default=False)
