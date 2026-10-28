# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column


class Profile(Base):
    __tablename__ = "koinon_profiles"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    subject: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120), default="")
    locale: Mapped[str] = mapped_column(String(64), default="en-US")
    time_zone: Mapped[str] = mapped_column(String(64), default="UTC")
    response_language: Mapped[str] = mapped_column(String(64), default="auto")
    avatar_bytes: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    avatar_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
