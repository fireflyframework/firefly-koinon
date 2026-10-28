# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


def timestamp():
    return datetime.now(UTC)


class KnowledgeIndex(Base):
    __tablename__ = "koinon_knowledge_indexes"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "domain", "native_workspace_id", "native_id", name="uq_koinon_index_native"
        ),
        UniqueConstraint("build_slot", name="uq_koinon_index_build"),
        UniqueConstraint("active_slot", name="uq_koinon_index_active"),
        CheckConstraint("domain in ('documents','structured')", name="ck_koinon_index_domain"),
        CheckConstraint("dimensions between 64 and 4096", name="ck_koinon_index_dimensions"),
        Index("ix_koinon_index_scope", "tenant_id", "workspace_id", "domain"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"))
    native_workspace_id: Mapped[str] = mapped_column(String(64))
    domain: Mapped[str] = mapped_column(String(32))
    native_id: Mapped[str] = mapped_column(String(64))
    provider_id: Mapped[str] = mapped_column(ForeignKey("koinon_providers.id"))
    provider_kind: Mapped[str] = mapped_column(String(32))
    provider_revision: Mapped[int] = mapped_column()
    model_id: Mapped[str] = mapped_column(String(255))
    dimensions: Mapped[int] = mapped_column()
    storage_dimensions: Mapped[int] = mapped_column()
    embedding_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    revision: Mapped[int] = mapped_column(default=1)
    build_slot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active_slot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cursor: Mapped[dict] = mapped_column(JSON, default=dict)
    transition: Mapped[dict] = mapped_column(JSON, default=dict)
    previous_binding: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    access_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    batch_size: Mapped[int] = mapped_column(default=32)
    chunk_count: Mapped[int] = mapped_column(default=0)
    vector_count: Mapped[int] = mapped_column(default=0)
    indexed: Mapped[bool] = mapped_column(default=False)
    qualification: Mapped[str] = mapped_column(String(64), default="probe_passed")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_by: Mapped[str] = mapped_column(String(512))
    updated_by: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
    ready_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
