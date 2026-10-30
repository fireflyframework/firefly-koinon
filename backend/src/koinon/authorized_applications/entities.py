# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column


class AuthorizedApplication(Base):
    __tablename__ = "koinon_authorized_applications"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(512), index=True)
    client_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(120))
    resource: Mapped[str] = mapped_column(String(2048))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    tenant_name: Mapped[str] = mapped_column(String(255))
    workspace_id: Mapped[str] = mapped_column(String(64))
    workspace_name: Mapped[str] = mapped_column(String(255))
    scopes: Mapped[list] = mapped_column(JSON)
    client_registration: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(UtcDateTime())
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)


def credential_matches(application, credential, now):
    return (
        application is not None
        and application.subject == credential.subject
        and application.revoked_at is None
        and application.expires_at > now
        and application.expires_at >= credential.expires_at
        and application.tenant_id == credential.tenant_id
        and [application.workspace_id] == credential.workspace_ids
        and set(application.scopes) == set(credential.scopes)
        and credential.asset_ids is None
    )
