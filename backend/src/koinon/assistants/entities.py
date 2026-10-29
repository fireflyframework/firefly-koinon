# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, ForeignKey, Index, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from koinon.assistants.history.entities import ChatFolder


def now() -> datetime:
    return datetime.now(UTC)


class Provider(Base):
    __tablename__ = "koinon_providers"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(32))
    api: Mapped[str | None] = mapped_column(String(16), nullable=True)
    base_url: Mapped[str] = mapped_column(String(2048))
    model_ids: Mapped[list] = mapped_column(JSON, default=list)
    secret_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    validated_revision: Mapped[int] = mapped_column(default=0)
    checks: Mapped[list] = mapped_column(JSON, default=list)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class AgentConfiguration(Base):
    __tablename__ = "koinon_agents"
    __table_args__ = (UniqueConstraint("tenant_id", "id", name="uq_koinon_agents_tenant_id"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("koinon_providers.id"))
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(String(2000), default="")
    model_id: Mapped[str] = mapped_column(String(255))
    model_options: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    tools: Mapped[list] = mapped_column(JSON, default=list)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    instructions: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(default=True)
    revision: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class ChatThread(Base):
    __tablename__ = "koinon_chat_threads"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    subject: Mapped[str] = mapped_column(String(512), index=True)
    title: Mapped[str] = mapped_column(String(160))
    title_source: Mapped[str] = mapped_column(String(16), default="default", server_default="default")
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    folder_id: Mapped[str | None] = mapped_column(
        ForeignKey(f"{ChatFolder.__tablename__}.id", ondelete="SET NULL"), nullable=True, index=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class ChatMessage(Base):
    __tablename__ = "koinon_chat_messages"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_threads.id"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="completed")
    presentation: Mapped[dict] = mapped_column(JSON, default=dict)
    citations: Mapped[list] = mapped_column(JSON, default=list)
    artifacts: Mapped[list] = mapped_column(JSON, default=list)
    answer_policy: Mapped[dict] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class ChatRun(Base):
    __tablename__ = "koinon_chat_runs"
    __table_args__ = (
        UniqueConstraint("thread_id", "client_request_id", name="uq_koinon_chat_request"),
        Index("ix_koinon_chat_queue", "status", "available_at"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), index=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_threads.id"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_messages.id"))
    user_message_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_messages.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("koinon_agents.id"))
    access_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_revision: Mapped[int] = mapped_column()
    provider_revision: Mapped[int] = mapped_column()
    knowledge_settings_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    client_request_id: Mapped[str] = mapped_column(String(255))
    payload_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    lease_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    available_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    attempts: Mapped[int] = mapped_column(default=0)
    sequence: Mapped[int] = mapped_column(default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class ChatEvent(Base):
    __tablename__ = "koinon_chat_events"
    __table_args__ = (UniqueConstraint("run_id", "sequence", name="uq_koinon_chat_event"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_runs.id"), index=True)
    sequence: Mapped[int] = mapped_column()
    type: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class ToolResult(Base):
    __tablename__ = "koinon_chat_tool_results"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    run_id: Mapped[str] = mapped_column(ForeignKey("koinon_chat_runs.id"), index=True)
    kind: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
