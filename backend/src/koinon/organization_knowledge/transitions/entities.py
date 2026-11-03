# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column


def now():
    return datetime.now(UTC)


class KnowledgeModeTransition(Base):
    __tablename__ = "koinon_knowledge_mode_transitions"
    __table_args__ = (
        UniqueConstraint("active_slot", name="uq_knowledge_mode_active"),
        UniqueConstraint("tenant_id", "id", name="uq_knowledge_mode_tenant_id"),
        Index("ix_knowledge_mode_tenant_created", "tenant_id", "created_at", "id"),
        CheckConstraint("revision >= 1", name="ck_knowledge_mode_revision"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    active_slot: Mapped[str | None] = mapped_column(String(64), nullable=True)
    job_id: Mapped[str] = mapped_column(ForeignKey("lattice_jobs.id"), unique=True)
    actor: Mapped[str] = mapped_column(String(512))
    access_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    base_revision: Mapped[int] = mapped_column()
    base_digest: Mapped[str] = mapped_column(String(64))
    active_mode: Mapped[str] = mapped_column(String(8))
    requested_settings: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    stage: Mapped[str] = mapped_column(String(32), default="discovery")
    revision: Mapped[int] = mapped_column(default=1)
    counters: Mapped[dict] = mapped_column(JSON, default=dict)
    stage_milliseconds: Mapped[dict] = mapped_column(JSON, default=dict)
    cursor: Mapped[dict] = mapped_column(JSON, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class KnowledgeModeTarget(Base):
    __tablename__ = "koinon_knowledge_mode_targets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "transition_id"],
            ["koinon_knowledge_mode_transitions.tenant_id", "koinon_knowledge_mode_transitions.id"],
        ),
        UniqueConstraint("transition_id", "kind", "catalog_id", name="uq_knowledge_mode_target"),
        Index("ix_knowledge_mode_target_page", "tenant_id", "transition_id", "status", "id"),
        Index("ix_knowledge_mode_target_cursor", "tenant_id", "transition_id", "id"),
        Index("ix_knowledge_mode_target_kind", "tenant_id", "transition_id", "kind", "id"),
        Index("ix_knowledge_mode_target_scope", "tenant_id", "transition_id", "workspace_id", "id"),
        Index(
            "ix_knowledge_mode_target_scope_kind", "tenant_id", "transition_id", "workspace_id", "kind", "id"
        ),
        CheckConstraint("kind in ('workspace','document','curated')", name="ck_knowledge_mode_target_kind"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    transition_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    catalog_id: Mapped[str] = mapped_column(String(64))
    workspace_id: Mapped[str] = mapped_column(String(64))
    native_workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    native_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    index_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class KnowledgeModeIndexAttempt(Base):
    __tablename__ = "koinon_knowledge_mode_index_attempts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "transition_id"],
            ["koinon_knowledge_mode_transitions.tenant_id", "koinon_knowledge_mode_transitions.id"],
        ),
        UniqueConstraint("tenant_id", "id", name="uq_mode_index_attempt_tenant"),
        UniqueConstraint("transition_id", "index_id", "attempt_revision", name="uq_mode_index_attempt"),
        Index("ix_mode_index_attempt_page", "tenant_id", "transition_id", "id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    transition_id: Mapped[str] = mapped_column(String(64))
    index_id: Mapped[str] = mapped_column(String(64))
    attempt_revision: Mapped[int] = mapped_column()
    workspace_id: Mapped[str] = mapped_column(String(64))
    native_workspace_id: Mapped[str] = mapped_column(String(64))
    native_id: Mapped[str] = mapped_column(String(64))
    job_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    provider_id: Mapped[str] = mapped_column(String(64))
    provider_revision: Mapped[int] = mapped_column()
    model_id: Mapped[str] = mapped_column(String(255))
    dimensions: Mapped[int] = mapped_column()
    storage_dimensions: Mapped[int] = mapped_column()
    embedding_fingerprint: Mapped[str] = mapped_column(String(64))
    actor: Mapped[str] = mapped_column(String(512))
    access_token_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    request: Mapped[dict] = mapped_column(JSON)
    previous_native_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


class KnowledgeModeIndexResolution(Base):
    __tablename__ = "koinon_knowledge_mode_index_resolutions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "id"],
            ["koinon_knowledge_mode_index_attempts.tenant_id", "koinon_knowledge_mode_index_attempts.id"],
        ),
        CheckConstraint(
            "status in ('pending','finished','restored','aborted')", name="ck_mode_index_resolution_status"
        ),
        CheckConstraint("revision >= 1", name="ck_mode_index_resolution_revision"),
        Index("ix_mode_index_resolution_pending", "tenant_id", "status", "id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=now)


def _install_attempt_guards(_metadata, connection, **_kwargs):
    from koinon.organization_knowledge.transitions.attempt_schema_v1 import install

    install(connection)


event.listen(Base.metadata, "after_create", _install_attempt_guards)
