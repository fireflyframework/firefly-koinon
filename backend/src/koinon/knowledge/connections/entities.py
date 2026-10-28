# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


def timestamp():
    return datetime.now(UTC)


class KnowledgeConnection(Base):
    __tablename__ = "koinon_knowledge_connections"
    __table_args__ = (
        UniqueConstraint("tenant_id", "scope_key", "domain", "role", name="uq_koinon_knowledge_role"),
        CheckConstraint("scope_key = coalesce(workspace_id, '')", name="ck_koinon_knowledge_scope"),
        CheckConstraint("mode in ('provider', 'current_agent')", name="ck_koinon_knowledge_mode"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(
        ForeignKey("lattice_catalog.id"), nullable=True, index=True
    )
    scope_key: Mapped[str] = mapped_column(String(64), default="")
    domain: Mapped[str] = mapped_column(String(32))
    role: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(24))
    provider_id: Mapped[str | None] = mapped_column(ForeignKey("koinon_providers.id"), nullable=True)
    model_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model_options: Mapped[dict] = mapped_column(JSON, default=dict)
    dimensions: Mapped[int | None] = mapped_column(nullable=True)
    storage_dimensions: Mapped[int | None] = mapped_column(nullable=True)
    space_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    embedding_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(default=1)
    created_by: Mapped[str] = mapped_column(String(512))
    updated_by: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=timestamp)
