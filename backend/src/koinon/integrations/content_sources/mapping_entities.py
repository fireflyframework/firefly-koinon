# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reviewed destinations and monotonic source-object observations; no credentials."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class SourceMapping(Base):
    __tablename__ = "koinon_content_mappings"
    __table_args__ = (
        Index("ix_content_mapping_owner", "tenant_id", "owner", "status"),
        CheckConstraint("revision BETWEEN 1 AND 2147483647", name="ck_content_mapping_revision"),
        CheckConstraint(
            "status in ('reviewed','active','paused','reconnect_required','retired')",
            name="ck_content_mapping_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    owner: Mapped[str] = mapped_column(String(512))
    connection_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_connections.id"), index=True)
    provider: Mapped[str] = mapped_column(String(32))
    external_subject: Mapped[str] = mapped_column(String(1024))
    external_tenant: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    issuer: Mapped[str] = mapped_column(String(2048))
    config_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    drive_id: Mapped[str] = mapped_column(String(1024))
    root_id: Mapped[str] = mapped_column(String(1024))
    workspace_id: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str] = mapped_column(String(64))
    parent_id: Mapped[str] = mapped_column(String(64))
    request_json: Mapped[dict] = mapped_column(JSON)
    request_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="reviewed")
    revision: Mapped[int] = mapped_column(default=1)
    reviewed_at: Mapped[datetime] = mapped_column(UtcDateTime())
    reviewed_expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceObject(Base):
    __tablename__ = "koinon_content_objects"
    __table_args__ = (
        UniqueConstraint("tenant_id", "mapping_id", "item_id", name="uq_content_mapping_object"),
        CheckConstraint("generation BETWEEN 1 AND 2147483647", name="ck_content_object_generation"),
        CheckConstraint("mapping_revision BETWEEN 1 AND 2147483647", name="ck_content_object_mapping"),
        CheckConstraint(
            "state in ('pending','imported','failed','deleted','removed','excluded')",
            name="ck_content_object_state",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    mapping_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_mappings.id"))
    item_id: Mapped[str] = mapped_column(String(1024))
    generation: Mapped[int] = mapped_column(default=1)
    mapping_revision: Mapped[int] = mapped_column()
    remote_version: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    state: Mapped[str] = mapped_column(String(32), default="pending")
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
