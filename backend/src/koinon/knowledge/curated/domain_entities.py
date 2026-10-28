# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native canon receipts/evidence and rebuildable projections; version.body owns content."""

from datetime import UTC, datetime

from flycanon.models.entities.base import Base
from pyfly.data.relational.sqlalchemy import UtcDateTime
from sqlalchemy import JSON, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Scoped:
    tenant_id: Mapped[str] = mapped_column(String(64))
    workspace_id: Mapped[str] = mapped_column(String(64))


class CuratedHeadRow(Scoped, Base):
    __tablename__ = "canon_curated_heads"
    __table_args__ = (
        UniqueConstraint("tenant_id", "canonical_item_id", name="uq_curated_canonical_item"),
        ForeignKeyConstraint(
            ["native_item_id", "serving_version"],
            ["canon_knowledge_versions.knowledge_item_id", "canon_knowledge_versions.version"],
        ),
        Index("ix_curated_serving_scope", "tenant_id", "workspace_id", "serving_version"),
    )
    native_item_id: Mapped[str] = mapped_column(ForeignKey("canon_knowledge_items.id"), primary_key=True)
    canonical_item_id: Mapped[str] = mapped_column(String(64))
    canonical_workspace_id: Mapped[str] = mapped_column(String(64))
    destination_id: Mapped[str] = mapped_column(String(64))
    serving_version: Mapped[int | None] = mapped_column(nullable=True)
    operation_id: Mapped[str] = mapped_column(String(64))


class CuratedCommitRow(Scoped, Base):
    __tablename__ = "canon_knowledge_commits"
    operation_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    canonical_item_id: Mapped[str] = mapped_column(String(64))
    subject: Mapped[str] = mapped_column(String(512))
    authorization_digest: Mapped[str] = mapped_column(String(64))
    originating_token_ids: Mapped[list] = mapped_column(JSON)
    receipt_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class CuratedEvidenceRow(Scoped, Base):
    __tablename__ = "canon_knowledge_version_evidence"
    native_version_id: Mapped[str] = mapped_column(
        ForeignKey("canon_knowledge_versions.id"), primary_key=True
    )
    ordinal: Mapped[int] = mapped_column(primary_key=True)
    operation_id: Mapped[str] = mapped_column(ForeignKey("canon_knowledge_commits.operation_id"))
    kind: Mapped[str] = mapped_column(String(32))
    sha256: Mapped[str] = mapped_column(String(64))
    evidence_json: Mapped[dict] = mapped_column(JSON)


class CuratedVersionChunkRow(Scoped, Base):
    __tablename__ = "canon_knowledge_version_chunks"
    __table_args__ = (
        UniqueConstraint("native_version_id", "ordinal", name="uq_curated_version_chunk"),
        Index("ix_curated_chunk_scope", "tenant_id", "workspace_id", "native_version_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    native_version_id: Mapped[str] = mapped_column(ForeignKey("canon_knowledge_versions.id"))
    canonical_item_id: Mapped[str] = mapped_column(String(64))
    ordinal: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    char_start: Mapped[int] = mapped_column()
    char_end: Mapped[int] = mapped_column()
