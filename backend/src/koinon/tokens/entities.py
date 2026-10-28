# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class PersonalToken(Base):
    __tablename__ = "koinon_personal_tokens"
    __table_args__ = (
        CheckConstraint(
            "(purpose = 'personal' AND authorized_application_id IS NULL) OR "
            "(purpose = 'application' AND authorized_application_id IS NOT NULL)",
            name="ck_token_purpose_application",
        ),
    )
    purpose: Mapped[str] = mapped_column(
        String(24), default="personal", server_default="personal", index=True
    )
    authorized_application_id: Mapped[str | None] = mapped_column(
        ForeignKey("koinon_authorized_applications.id"), nullable=True, index=True
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(512), index=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    token_hash: Mapped[str] = mapped_column(String(64))
    prefix: Mapped[str] = mapped_column(String(64))
    scopes: Mapped[list] = mapped_column(JSON)
    workspace_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    asset_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    resource_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
