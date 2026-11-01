# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator-only progress is separate from user identity and organization authority."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import DDL, JSON, CheckConstraint, ForeignKey, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from koinon.installation.guards import ledger_guards


class InstallationRun(Base):
    __tablename__ = "koinon_installation_runs"
    __table_args__ = (
        UniqueConstraint("installation_id", "tenant_id", "plan_key", name="uq_installation_plan"),
        CheckConstraint("status IN ('running','partial','completed')", name="ck_installation_status"),
        CheckConstraint("generation >= 1", name="ck_installation_generation"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    installation_id: Mapped[str] = mapped_column(ForeignKey("koinon_installation_identity.installation_id"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    plan_key: Mapped[str] = mapped_column(String(64))
    plan_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20))
    generation: Mapped[int] = mapped_column(default=1)
    owner_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    checkpoints: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())


for dialect in ("sqlite", "postgresql"):
    for statement in ledger_guards(dialect):
        event.listen(InstallationRun.__table__, "after_create", DDL(statement).execute_if(dialect=dialect))
