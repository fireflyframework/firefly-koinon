# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Append-only generation-bound personal memory manifests."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column


class ChatMemoryManifest(Base):
    __tablename__ = "koinon_chat_memory_manifests"
    __table_args__ = (Index("ix_koinon_chat_memory_owner", "tenant_id", "subject", "thread_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    generation_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_tool_results.id"), unique=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_runs.id"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    subject: Mapped[str] = mapped_column(String(512))
    thread_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_threads.id"))
    folder_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    policy_version: Mapped[int] = mapped_column(default=1)
    start_sequence: Mapped[int] = mapped_column()
    scope_sha256: Mapped[str] = mapped_column(String(64))
    manifest_json: Mapped[dict] = mapped_column(JSON)
    manifest_sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
