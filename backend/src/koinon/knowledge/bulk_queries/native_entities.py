# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime
from uuid import UUID

from flyquery.models.entities import Base
from pyfly.data.relational.sqlalchemy import UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from koinon.knowledge.bulk.entities import now


class NativeQueryOperation(Base):
    __tablename__ = "flyquery_bulk_query_operations"
    __table_args__ = (
        CheckConstraint("status IN ('admitted','committed')", name="ck_bulk_query_operation_status"),
        CheckConstraint(
            "(status = 'admitted' AND receipt_json IS NULL AND query_id IS NULL) OR "
            "(status = 'committed' AND receipt_json IS NOT NULL AND query_id IS NOT NULL)",
            name="ck_bulk_query_operation_receipt",
        ),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(512))
    workspace_id: Mapped[UUID] = mapped_column(Uuid)
    dataset_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("flyquery_datasets.id"))
    catalog_workspace_id: Mapped[str] = mapped_column(String(64))
    catalog_dataset_id: Mapped[str] = mapped_column(String(64))
    question: Mapped[str] = mapped_column(String(8000))
    policy_sha256: Mapped[str] = mapped_column(String(64))
    connections_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="admitted")
    query_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("flyquery_queries.id"), nullable=True, unique=True
    )
    receipt_json: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
