# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from koinon.knowledge.bulk.entities import BulkBatch


class ExternalReviewRow(Base):
    __tablename__ = "koinon_external_knowledge_reviews"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "subject", "credential_id", "stage_key", name="uq_external_review_stage"
        ),
        Index("ix_external_review_owner", "tenant_id", "subject", "status"),
    )
    id: Mapped[str] = mapped_column(ForeignKey("koinon_knowledge_intents.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    workspace_id: Mapped[str] = mapped_column(String(64))
    credential_id: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credential_sha256: Mapped[str] = mapped_column(String(64))
    stage_key: Mapped[str] = mapped_column(String(128))
    request_sha256: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column()
    authorization_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
    nonce_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


class ExternalFileReviewRow(Base):
    __tablename__ = "koinon_external_file_reviews"
    __table_args__ = (
        UniqueConstraint("tenant_id", "subject", "credential_id", "stage_key", name="uq_external_file_stage"),
        Index("ix_external_file_owner", "tenant_id", "subject", "status"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    credential_id: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credential_sha256: Mapped[str] = mapped_column(String(64))
    stage_key: Mapped[str] = mapped_column(String(128))
    request_json: Mapped[dict] = mapped_column(JSON)
    destination_json: Mapped[dict] = mapped_column(JSON)
    authorization_digest: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32))
    chunks_json: Mapped[dict] = mapped_column(JSON, default=dict)
    blob_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blob_reference_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    bulk_batch_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(BulkBatch.id, name="fk_external_file_bulk_batch"), nullable=True
    )
    nonce_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmation_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    receipt_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    decided_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    gc_status: Mapped[str] = mapped_column(String(16), default="none")
    gc_cursor: Mapped[int] = mapped_column(default=0)
