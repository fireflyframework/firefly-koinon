# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class EvidenceReview(Base):
    __tablename__ = "koinon_evidence_reviews"
    __table_args__ = (Index("ix_koinon_review_owner_expiry", "tenant_id", "owner_subject", "expires_at"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    owner_subject: Mapped[str] = mapped_column(String(512))
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    revision: Mapped[str] = mapped_column(String(64))
    request_json: Mapped[dict] = mapped_column(JSON)
    snapshot_json: Mapped[dict] = mapped_column(JSON)
    manifest_json: Mapped[list] = mapped_column(JSON)
    creator_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    consumed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
