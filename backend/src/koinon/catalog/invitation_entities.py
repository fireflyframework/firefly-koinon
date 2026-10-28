# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class Invitation(Base):
    __tablename__ = "koinon_invitations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    workspace_id: Mapped[str | None] = mapped_column(ForeignKey("lattice_catalog.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32))
    label: Mapped[str] = mapped_column(String(120), default="")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    accepted_by: Mapped[str | None] = mapped_column(String(512), nullable=True)
