# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy import text as sql_text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class VersionedBase(DeclarativeBase):
    """Additive vector-sidecar metadata; the original entity metadata remains stable."""


class EmbeddingSet(VersionedBase):
    __tablename__ = "flyquery_embedding_sets"
    __table_args__ = (
        CheckConstraint("dimensions between 64 and 1536", name="ck_structured_set_width"),
        Index("ix_structured_set_scope", "tenant_id", "workspace_id"),
        Index(
            "uq_structured_active_set",
            "tenant_id",
            "workspace_id",
            unique=True,
            postgresql_where=sql_text("status='active'"),
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(255))
    dimensions: Mapped[int] = mapped_column(Integer)
    config_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="building")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sql_text("now()"))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(512))


class EmbeddingVector(VersionedBase):
    __tablename__ = "flyquery_embedding_vectors"
    __table_args__ = (
        CheckConstraint("kind in ('schema','example')", name="ck_structured_vector_kind"),
        Index("ix_structured_vector_scope", "tenant_id", "workspace_id", "set_id"),
    )
    set_id: Mapped[str] = mapped_column(ForeignKey("flyquery_embedding_sets.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    object_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(PG_UUID(as_uuid=True), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64))
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    model: Mapped[str] = mapped_column(String(255))
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=sql_text("now()"))
