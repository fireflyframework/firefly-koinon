# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class ChatFolder(Base):
    __tablename__ = "koinon_chat_folders"
    __table_args__ = (Index("ix_koinon_chat_folder_owner", "tenant_id", "subject", "parent_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    name: Mapped[str] = mapped_column(String(120))
    scope: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("koinon_chat_folders.id", ondelete="SET NULL"), nullable=True
    )
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
