# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from koinon.knowledge.bulk.entities import now


class QueryBatch(Base):
    __tablename__ = "koinon_query_batches"
    __table_args__ = (
        UniqueConstraint("tenant_id", "key_hash", name="uq_query_batch_key"),
        Index("ix_query_batch_owner", "tenant_id", "subject", "created_at", "id"),
        CheckConstraint("revision BETWEEN 1 AND 2147483647", name="ck_query_batch_revision"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_tenants.id"))
    workspace_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"))
    subject: Mapped[str] = mapped_column(String(512))
    token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    key_hash: Mapped[str] = mapped_column(String(64))
    request_hash: Mapped[str] = mapped_column(String(64))
    request_json: Mapped[dict] = mapped_column(JSON)
    actions_json: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(default=1)
    cancelled: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())


class QueryBatchItem(Base):
    __tablename__ = "koinon_query_batch_items"
    __table_args__ = (
        UniqueConstraint("batch_id", "ordinal", name="uq_query_item_ordinal"),
        UniqueConstraint("batch_id", "client_item_id", name="uq_query_item_client"),
        Index("ix_query_item_page", "batch_id", "ordinal", "id"),
        CheckConstraint("ordinal BETWEEN 0 AND 19", name="ck_query_item_ordinal"),
        CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled','reconciling')",
            name="ck_query_item_status",
        ),
        CheckConstraint("status != 'succeeded' OR result_json IS NOT NULL", name="ck_query_item_receipt"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_query_batches.id"))
    ordinal: Mapped[int] = mapped_column()
    client_item_id: Mapped[str] = mapped_column(String(64))
    dataset_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"))
    question: Mapped[str] = mapped_column(String(8000))
    native_workspace_id: Mapped[str] = mapped_column(String(64))
    native_dataset_id: Mapped[str] = mapped_column(String(64))
    connection_json: Mapped[dict] = mapped_column(JSON)
    policy_json: Mapped[dict] = mapped_column(JSON)
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_jobs.id"), unique=True)
    status: Mapped[str] = mapped_column(String(24), default="queued")
    result_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)


class QueryBatchReference(Base):
    __tablename__ = "koinon_query_batch_references"
    __table_args__ = (UniqueConstraint("item_id", "native_table_id", name="uq_query_reference_native"),)
    item_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("koinon_query_batch_items.id"), primary_key=True
    )
    catalog_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_catalog.id"), primary_key=True)
    native_table_id: Mapped[str] = mapped_column(String(64))
    snapshot_id: Mapped[str] = mapped_column(String(64))
    qualified_name: Mapped[str] = mapped_column(String(512))
