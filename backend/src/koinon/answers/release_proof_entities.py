# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private, append-only identity attestations; no evidence content or access grants."""

from datetime import datetime
from typing import cast

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    LargeBinary,
    String,
    Table,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from koinon.assistants.entities import ChatMessage, ChatRun, ChatThread, ToolResult
from koinon.catalog.entities import Tenant


class AnswerReleaseProof(Base):
    __tablename__ = "koinon_answer_release_proofs"
    __table_args__ = (
        CheckConstraint("projection_version = 1", name="ck_release_proof_version"),
        CheckConstraint(
            "pin_count BETWEEN 0 AND 100 AND source_count BETWEEN 0 AND 500", name="ck_release_proof_counts"
        ),
        CheckConstraint(
            "reset_sequence >= 0 AND publication_sequence > reset_sequence", name="ck_release_proof_sequences"
        ),
        CheckConstraint("writer_kind IN ('publication','backfill')", name="ck_release_proof_writer"),
        CheckConstraint(
            "octet_length(state_sha256)=32 AND octet_length(canonical_seal_sha256)=32 AND "
            "octet_length(release_native_sha256)=32 AND octet_length(message_native_sha256)=32 AND "
            "octet_length(selection_native_sha256)=32 AND octet_length(active_selector_sha256)=32",
            name="ck_release_proof_hashes",
        ),
        Index("ix_release_proof_context", "tenant_id", "run_id", "message_id", "projection_version"),
    )
    release_result_id: Mapped[str] = mapped_column(
        ForeignKey(ToolResult.id, ondelete="RESTRICT"), primary_key=True
    )
    projection_version: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey(Tenant.id, ondelete="RESTRICT"))
    thread_id: Mapped[str] = mapped_column(ForeignKey(ChatThread.id, ondelete="RESTRICT"))
    owner_subject: Mapped[str] = mapped_column(String(512))
    run_id: Mapped[str] = mapped_column(ForeignKey(ChatRun.id, ondelete="RESTRICT"))
    message_id: Mapped[str] = mapped_column(ForeignKey(ChatMessage.id, ondelete="RESTRICT"))
    user_message_id: Mapped[str] = mapped_column(ForeignKey(ChatMessage.id, ondelete="RESTRICT"))
    generation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    generation_start_sequence: Mapped[int | None] = mapped_column(nullable=True)
    generation_created_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    reset_sequence: Mapped[int] = mapped_column()
    publication_sequence: Mapped[int] = mapped_column()
    policy_version: Mapped[str] = mapped_column(String(32))
    outcome: Mapped[str] = mapped_column(String(32))
    canonical_seal_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    release_native_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    message_native_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    selection_native_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    active_selector_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    state_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    pin_count: Mapped[int] = mapped_column()
    source_count: Mapped[int] = mapped_column()
    provenance_complete: Mapped[bool] = mapped_column()
    verifier: Mapped[str] = mapped_column(String(64))
    writer_kind: Mapped[str] = mapped_column(String(16))
    worker_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    attempt: Mapped[int | None] = mapped_column(nullable=True)
    maintenance_claim_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())


class AnswerReleaseProofPin(Base):
    __tablename__ = "koinon_answer_release_proof_pins"
    __table_args__ = (
        ForeignKeyConstraint(
            ["release_result_id", "projection_version"],
            [
                "koinon_answer_release_proofs.release_result_id",
                "koinon_answer_release_proofs.projection_version",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "octet_length(canonical_sha256)=32 AND octet_length(native_sha256)=32",
            name="ck_release_pin_hashes",
        ),
    )
    release_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    projection_version: Mapped[int] = mapped_column(primary_key=True)
    result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    result_kind: Mapped[str] = mapped_column(String(32))
    canonical_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))
    native_sha256: Mapped[bytes] = mapped_column(LargeBinary(32))


class AnswerReleaseProofSource(Base):
    __tablename__ = "koinon_answer_release_proof_sources"
    __table_args__ = (
        ForeignKeyConstraint(
            ["release_result_id", "projection_version"],
            [
                "koinon_answer_release_proofs.release_result_id",
                "koinon_answer_release_proofs.projection_version",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("kind IN ('document','dataset','knowledge_version')", name="ck_release_source_kind"),
        CheckConstraint(
            "source_part_sha256 IS NULL OR octet_length(source_part_sha256)=32", name="ck_release_source_hash"
        ),
        CheckConstraint("recorded_page IS NULL OR recorded_page>0", name="ck_release_source_page"),
    )
    release_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    projection_version: Mapped[int] = mapped_column(primary_key=True)
    source_reference_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    asset_id: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extraction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_part_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_part_sha256: Mapped[bytes | None] = mapped_column(LargeBinary(32), nullable=True)
    used_revision: Mapped[str | None] = mapped_column(String(128), nullable=True)
    recorded_page: Mapped[int | None] = mapped_column(nullable=True)
    page_basis: Mapped[str | None] = mapped_column(String(32), nullable=True)
    knowledge_item_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    knowledge_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    knowledge_version: Mapped[int | None] = mapped_column(nullable=True)
    snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    supporting_result_ids: Mapped[list] = mapped_column(JSON)


class AnswerReleaseProjectionJob(Base):
    __tablename__ = "koinon_answer_release_projection_jobs"
    __table_args__ = (
        CheckConstraint("projection_version=1 AND revision>=1", name="ck_release_job_revision"),
        CheckConstraint("state IN ('ready','running','blocked','complete')", name="ck_release_job_state"),
        CheckConstraint(
            "scanned>=0 AND projected>=0 AND already_present>=0 AND invalid>=0 AND blocked>=0",
            name="ck_release_job_counts",
        ),
        CheckConstraint(
            "json_typeof(error_sample)='array' AND json_array_length(error_sample)<=25 AND "
            "octet_length(error_sample::text)<=4096",
            name="ck_release_job_errors",
        ).ddl_if(dialect="postgresql"),
    )
    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    projection_version: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cursor_created_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    cursor_release_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    high_water_created_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    high_water_release_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    state: Mapped[str] = mapped_column(String(16))
    claim_token: Mapped[str | None] = mapped_column(String(64), nullable=True)
    claim_until: Mapped[datetime | None] = mapped_column(UtcDateTime(), nullable=True)
    revision: Mapped[int] = mapped_column()
    scanned: Mapped[int] = mapped_column()
    projected: Mapped[int] = mapped_column()
    already_present: Mapped[int] = mapped_column()
    invalid: Mapped[int] = mapped_column()
    blocked: Mapped[int] = mapped_column()
    error_sample: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime())


PROOF_TABLES = tuple(
    cast(Table, model.__table__)
    for model in (
        AnswerReleaseProof,
        AnswerReleaseProofPin,
        AnswerReleaseProofSource,
        AnswerReleaseProjectionJob,
    )
)


@event.listens_for(Base.metadata, "after_create")
def install_release_proof_guards(metadata, connection, **kwargs):
    if connection.dialect.name != "postgresql":
        return
    created = {table.name for table in kwargs.get("tables", ())}
    if not {table.name for table in PROOF_TABLES}.issubset(created):
        return
    from koinon.answers.release_proof_guards import guard_statements

    for statement in guard_statements():
        connection.execute(text(statement))
