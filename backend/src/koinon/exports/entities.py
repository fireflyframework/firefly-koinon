# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class ExportRecord(Base):
    __tablename__ = "koinon_exports"
    __table_args__ = (Index("ix_koinon_export_owner_expiry", "tenant_id", "owner_subject", "expires_at"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    review_id: Mapped[str] = mapped_column(ForeignKey("koinon_evidence_reviews.id"), unique=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    owner_subject: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    cancelled_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
