# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class ExternalReadReceiptRow(Base):
    __tablename__ = "koinon_mcp_read_receipts"
    __table_args__ = (Index("ix_mcp_read_receipt_owner", "tenant_id", "subject", "expires_at"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    credential_id: Mapped[str] = mapped_column(String(64))
    application_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    credential_sha256: Mapped[str] = mapped_column(String(64))
    operation: Mapped[str] = mapped_column(String(16))
    request_sha256: Mapped[str] = mapped_column(String(64))
    result_sha256: Mapped[str] = mapped_column(String(64))
    sources_json: Mapped[list] = mapped_column(JSON)
    provenance_json: Mapped[dict] = mapped_column(JSON)
    receipt_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
