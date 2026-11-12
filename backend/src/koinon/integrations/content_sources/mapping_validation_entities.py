# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Expiring, encrypted mapping preparation; never approval or publication authority."""

from datetime import UTC, datetime
from uuid import UUID

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import (
    BigInteger,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column


class SourceMappingValidation(Base):
    __tablename__ = "koinon_content_mapping_validations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "id", name="uq_content_validation_scope"),
        UniqueConstraint("tenant_id", "owner", "operation_id", name="uq_content_validation_operation"),
        ForeignKeyConstraint(
            ["tenant_id", "owner", "connection_id"],
            [
                "koinon_content_connections.tenant_id",
                "koinon_content_connections.owner",
                "koinon_content_connections.id",
            ],
            name="fk_content_validation_connection",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "owner", "mapping_id"],
            [
                "koinon_content_mappings.tenant_id",
                "koinon_content_mappings.owner",
                "koinon_content_mappings.id",
            ],
            name="fk_content_validation_mapping",
        ),
        Index("ix_content_validation_owner", "tenant_id", "owner", "created_at", "id"),
        Index("ix_content_validation_connection", "connection_id"),
        Index("ix_content_validation_mapping", "mapping_id"),
        Index("ix_content_validation_expiry", "expires_at", "tenant_id", "id"),
        Index(
            "ix_content_validation_cleanup",
            text("cleanup_last_attempt_at NULLS FIRST"),
            "tenant_id",
            "id",
            postgresql_where=text("state='cleaning'"),
        ).ddl_if(dialect="postgresql"),
    )
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    owner: Mapped[str] = mapped_column(String(512))
    operation_id: Mapped[UUID] = mapped_column(Uuid)
    session_hash: Mapped[str] = mapped_column(String(64))
    request_sha256: Mapped[str] = mapped_column(String(64))
    request_ciphertext: Mapped[bytes | None]
    connection_id: Mapped[str] = mapped_column(String(64))
    connection_revision: Mapped[int]
    authority_sha256: Mapped[str] = mapped_column(String(64))
    mapping_id: Mapped[str | None] = mapped_column(String(64))
    expected_revision: Mapped[int | None]
    root_captured: Mapped[bool] = mapped_column(default=False, server_default="false")
    root_kind: Mapped[str | None] = mapped_column(String(16))
    root_proof_sha256: Mapped[str | None] = mapped_column(String(64))
    root_proof_ciphertext: Mapped[bytes | None]
    walk_ciphertext: Mapped[bytes | None]
    checkpoint_ciphertext: Mapped[bytes | None]
    state: Mapped[str] = mapped_column(String(32), default="scanning", server_default="scanning")
    revision: Mapped[int] = mapped_column(default=1, server_default="1")
    enumeration_complete: Mapped[bool] = mapped_column(default=False, server_default="false")
    verification_position: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    raw_observed_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    eligible_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    change_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    scan_max_items: Mapped[int]
    max_active_per_tenant: Mapped[int] = mapped_column(default=8, server_default="8")
    max_active_per_owner: Mapped[int] = mapped_column(default=2, server_default="2")
    max_records_per_tenant: Mapped[int] = mapped_column(default=1000, server_default="1000")
    max_retained_bytes_per_tenant: Mapped[int] = mapped_column(
        BigInteger, default=17179869184, server_default="17179869184"
    )
    reserved_bytes: Mapped[int] = mapped_column(BigInteger)
    payload_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    payload_released_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    manifest_sha256: Mapped[str | None] = mapped_column(String(64))
    last_continuation_sha256: Mapped[str | None] = mapped_column(String(64))
    last_continuation_result_revision: Mapped[int | None]
    reason_code: Mapped[str | None] = mapped_column(String(64))
    cleanup_reason: Mapped[str | None] = mapped_column(String(32))
    cleanup_position: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    cleanup_claim_token: Mapped[UUID | None] = mapped_column(Uuid)
    cleanup_claim_until: Mapped[datetime | None] = mapped_column(UtcDateTime())
    cleanup_last_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime())


class SourceMappingValidationEntry(Base):
    __tablename__ = "koinon_content_mapping_validation_entries"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "validation_id"],
            ["koinon_content_mapping_validations.tenant_id", "koinon_content_mapping_validations.id"],
            name="fk_content_validation_entry_scope",
        ),
        UniqueConstraint("tenant_id", "validation_id", "sequence", name="uq_content_validation_sequence"),
        Index("ix_content_validation_destination", "tenant_id", "validation_id", "destination_key_sha256"),
    )
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    validation_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    item_id: Mapped[str] = mapped_column(String(1024), primary_key=True)
    sequence: Mapped[int] = mapped_column(BigInteger)
    parent_item_id: Mapped[str | None] = mapped_column(String(1024))
    fingerprint_sha256: Mapped[str] = mapped_column(String(64))
    candidate_ciphertext: Mapped[bytes]
    destination_key_sha256: Mapped[str] = mapped_column(String(64))
    verified: Mapped[bool] = mapped_column(default=False, server_default="false")
    payload_bytes: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
