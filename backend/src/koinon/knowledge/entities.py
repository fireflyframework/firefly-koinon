# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class DomainBinding(Base):
    __tablename__ = "lattice_domain_bindings"
    __table_args__ = (
        UniqueConstraint("tenant_id", "catalog_id", "domain", name="uq_lattice_domain_binding"),
        Index("ix_lattice_native_binding", "tenant_id", "domain", "native_workspace_id", "native_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    catalog_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    domain: Mapped[str] = mapped_column(String(32))
    entity_kind: Mapped[str] = mapped_column(String(32))
    native_id: Mapped[str] = mapped_column(String(64))
    native_workspace_id: Mapped[str] = mapped_column(String(64))
    details_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
