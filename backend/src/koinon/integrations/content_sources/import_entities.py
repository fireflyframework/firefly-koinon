# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private intake origin bindings retained before and after native commit."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class SourceImportAttempt(Base):
    __tablename__ = "koinon_content_imports"
    __table_args__ = (
        UniqueConstraint("tenant_id", "object_id", "generation", name="uq_content_import_generation"),
        UniqueConstraint("intake_item_id", name="uq_content_import_intake"),
        CheckConstraint("generation BETWEEN 1 AND 2147483647", name="ck_content_import_generation"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    mapping_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_mappings.id"))
    mapping_revision: Mapped[int] = mapped_column()
    object_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_objects.id"))
    generation: Mapped[int] = mapped_column()
    intake_item_id: Mapped[str] = mapped_column(ForeignKey("koinon_bulk_items.id"))
    provider: Mapped[str] = mapped_column(String(32))
    external_subject: Mapped[str] = mapped_column(String(1024))
    external_tenant: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    drive_id: Mapped[str] = mapped_column(String(1024))
    remote_item_id: Mapped[str] = mapped_column(String(1024))
    remote_version: Mapped[str] = mapped_column(String(2048))
    source_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column()
    receipt_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    committed_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
