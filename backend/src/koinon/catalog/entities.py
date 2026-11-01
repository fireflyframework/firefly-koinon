# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared identities and provenance across both knowledge domains."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.system_guards import system_space_guards

INTERNAL_METADATA_KEYS = frozenset({"_koinon_lifecycle", "_koinon_intake", "_koinon_external_review"})


class Tenant(Base):
    __tablename__ = "lattice_tenants"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class CatalogEntry(Base):
    __tablename__ = "lattice_catalog"
    __table_args__ = (
        Index("ix_lattice_scope_kind", "tenant_id", "workspace_id", "kind"),
        UniqueConstraint("tenant_id", "system_key", name="uq_catalog_system_key"),
        CheckConstraint(
            "system_key IS NULL OR (kind='workspace' AND parent_id IS NULL "
            "AND workspace_id=id AND project_id IS NULL AND installation_run_id IS NOT NULL)",
            name="ck_catalog_system_workspace",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("lattice_catalog.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(4000), default="")
    status: Mapped[str] = mapped_column(String(32), default="ready")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(512))
    updated_by: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    system_key: Mapped[str | None] = mapped_column(String(64), nullable=True)
    installation_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Membership(Base):
    __tablename__ = "lattice_memberships"
    __table_args__ = (
        UniqueConstraint("subject", "tenant_id", "workspace_id", name="uq_lattice_membership_scope"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(512), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("lattice_catalog.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class AuditEvent(Base):
    __tablename__ = "lattice_audit"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    subject: Mapped[str] = mapped_column(String(512))
    action: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


for dialect in ("sqlite", "postgresql"):
    for statement in system_space_guards(dialect):
        event.listen(CatalogEntry.__table__, "after_create", DDL(statement).execute_if(dialect=dialect))
