# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private operational review state; no repository knowledge is stored here."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class KnowledgeIntentRow(Base):
    __tablename__ = "koinon_knowledge_intents"
    __table_args__ = (
        Index("ix_knowledge_intent_owner", "tenant_id", "subject", "status"),
        UniqueConstraint("tenant_id", "subject", "confirmation_key", name="uq_knowledge_confirmation_key"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    revision: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(32), default="preview")
    request_json: Mapped[dict] = mapped_column(JSON)
    destination_json: Mapped[dict] = mapped_column(JSON)
    evidence_json: Mapped[list] = mapped_column(JSON)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    target_item_id: Mapped[str] = mapped_column(String(64))
    authorization_digest: Mapped[str] = mapped_column(String(64))
    originating_token_ids: Mapped[list] = mapped_column(JSON, default=list)
    preview_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirming_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    confirmation_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    receipt_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())


class CuratedCatalogState(Base):
    __tablename__ = "koinon_curated_catalog_state"
    item_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    workspace_id: Mapped[str] = mapped_column(String(64), index=True)
    native_item_id: Mapped[str] = mapped_column(String(64))
    native_workspace_id: Mapped[str] = mapped_column(String(64))
    head_version: Mapped[int] = mapped_column()
    head_version_id: Mapped[str] = mapped_column(String(64))
    head_operation_id: Mapped[str] = mapped_column(String(64))
    serving_version: Mapped[int | None] = mapped_column(nullable=True)
    serving_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    serving_operation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    root_count: Mapped[int] = mapped_column(default=0)


class CuratedSourceRoot(Base):
    __tablename__ = "koinon_curated_source_roots"
    __table_args__ = (
        UniqueConstraint("item_id", "native_version_id", "source_asset_id", name="uq_curated_root"),
        Index("ix_curated_root_version", "tenant_id", "item_id", "native_version_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    item_id: Mapped[str] = mapped_column(ForeignKey("koinon_curated_catalog_state.item_id"))
    native_version_id: Mapped[str] = mapped_column(String(64))
    source_asset_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"))
