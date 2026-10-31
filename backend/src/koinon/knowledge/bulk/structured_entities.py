# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from uuid import UUID

from flyquery.models.entities import Base
from pyfly.data.relational.sqlalchemy import UtcDateTime
from sqlalchemy import JSON, BigInteger, CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from koinon.knowledge.bulk.entities import now


class StructuredBulkOperation(Base):
    __tablename__ = "flyquery_bulk_operations"
    __table_args__ = (
        CheckConstraint("status IN ('admitted','prepared','committed')", name="ck_structured_bulk_status"),
        CheckConstraint(
            "status = 'admitted' OR (plan_json IS NOT NULL AND prepared_json IS NOT NULL)",
            name="ck_structured_bulk_complete",
        ),
        CheckConstraint(
            "receipt_json IS NULL OR status = 'committed'", name="ck_structured_bulk_receipt_state"
        ),
        CheckConstraint(
            "status != 'prepared' OR prepared_json IS NOT NULL", name="ck_structured_bulk_prepared"
        ),
        CheckConstraint(
            "status != 'committed' OR receipt_json IS NOT NULL", name="ck_structured_bulk_receipt"
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(512))
    workspace_id: Mapped[UUID] = mapped_column(Uuid)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("flyquery_datasets.id"), unique=True)
    file_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    actor: Mapped[str] = mapped_column(String(512))
    catalog_source_id: Mapped[str] = mapped_column(String(64))
    catalog_dataset_id: Mapped[str] = mapped_column(String(64))
    catalog_file_version_id: Mapped[str] = mapped_column(String(64))
    filename: Mapped[str] = mapped_column(String(255))
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(24), default="admitted")
    plan_json: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    prepared_json: Mapped[list | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    receipt_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
