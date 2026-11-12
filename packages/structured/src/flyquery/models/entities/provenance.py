# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private retained provenance; callers cannot supply these authority records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from flyquery.models.entities import Base


class SourceMetadataProvenance(Base):
    __tablename__ = "flyquery_metadata_provenance"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "workspace_id",
            "created_by",
            "producer_kind",
            "producer_operation_id",
            "producer_ordinal",
            name="uq_metadata_producer",
        ),
        Index("ix_metadata_provenance_scope", "tenant_id", "workspace_id", "entity_kind", "entity_id", "id"),
    )
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    workspace_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    entity_kind: Mapped[str] = mapped_column(String, nullable=False)
    entity_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    semantic_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    manifest_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    producer_kind: Mapped[str] = mapped_column(String, nullable=False)
    producer_operation_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    producer_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    producer_size: Mapped[int] = mapped_column(Integer, nullable=False)
    request_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
