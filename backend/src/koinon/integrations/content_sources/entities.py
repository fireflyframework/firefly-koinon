# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private delegated grants; never use the importing account as a reader identity."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, Index, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column


class PersonalSourceConnection(Base):
    __tablename__ = "koinon_content_connections"
    __table_args__ = (
        Index("ix_content_connection_owner", "tenant_id", "owner"),
        CheckConstraint("provider in ('sharepoint','onedrive','google_drive')", name="ck_content_provider"),
        CheckConstraint(
            "status in ('pending','connected','reconnect_required','disconnected')",
            name="ck_content_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    owner: Mapped[str] = mapped_column(String(512))
    provider: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    revision: Mapped[int] = mapped_column(default=1)
    config_fingerprint: Mapped[str] = mapped_column(String(64), default="")
    external_subject: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    external_tenant: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    refresh_operation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    refresh_expires_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceAuthorizationChallenge(Base):
    __tablename__ = "koinon_content_authorizations"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending','exchanging','completed')", name="ck_content_authorization_status"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_connections.id"), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    owner: Mapped[str] = mapped_column(String(512))
    session_hash: Mapped[str] = mapped_column(String(64))
    state_hash: Mapped[str] = mapped_column(String(64), unique=True)
    config_fingerprint: Mapped[str] = mapped_column(String(64))
    connection_revision: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
