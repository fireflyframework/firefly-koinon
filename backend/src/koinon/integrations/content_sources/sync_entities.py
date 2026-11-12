# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable sync contracts; execution is leased through canonical Jobs."""

from datetime import UTC, datetime
from uuid import UUID

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column


class SourceMappingPolicy(Base):
    __tablename__ = "koinon_content_policies"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "owner", "mapping_id"],
            [
                "koinon_content_mappings.tenant_id",
                "koinon_content_mappings.owner",
                "koinon_content_mappings.id",
            ],
        ),
        UniqueConstraint("tenant_id", "mapping_id", "id", name="uq_content_policy_identity"),
        UniqueConstraint("tenant_id", "mapping_id", "revision", name="uq_content_policy_revision"),
        Index("ix_content_policy_owner", "tenant_id", "owner", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(512))
    mapping_id: Mapped[str] = mapped_column(String(64))
    revision: Mapped[int]
    mapping_revision: Mapped[int]
    authority_sha256: Mapped[str] = mapped_column(String(64))
    policy_json: Mapped[dict] = mapped_column(JSON)
    policy_sha256: Mapped[str] = mapped_column(String(64))
    root_ancestry_json: Mapped[list[str]] = mapped_column(JSON)
    review_id: Mapped[str] = mapped_column(String(64))
    review_digest: Mapped[str] = mapped_column(String(64))
    review_expires_at: Mapped[datetime] = mapped_column(UtcDateTime())
    accepted_by: Mapped[str | None] = mapped_column(String(512))
    accepted_session_hash: Mapped[str | None] = mapped_column(String(64))
    accepted_operation_id: Mapped[str | None] = mapped_column(String(64))
    accepted_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourcePolicyOperation(Base):
    """Retained policy review/apply receipt, separate from operational controls."""

    __tablename__ = "koinon_content_policy_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "owner", "mapping_id"],
            [
                "koinon_content_mappings.tenant_id",
                "koinon_content_mappings.owner",
                "koinon_content_mappings.id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "policy_id"],
            [
                "koinon_content_policies.tenant_id",
                "koinon_content_policies.mapping_id",
                "koinon_content_policies.id",
            ],
        ),
        UniqueConstraint("tenant_id", "owner", "operation_id", name="uq_content_policy_operation"),
        Index("ix_content_policy_operation_policy", "tenant_id", "mapping_id", "policy_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(512))
    operation_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    mapping_id: Mapped[str] = mapped_column(String(64))
    policy_id: Mapped[str] = mapped_column(String(64))
    expected_policy_revision: Mapped[int | None]
    result_policy_revision: Mapped[int]
    payload_sha256: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceSyncState(Base):
    __tablename__ = "koinon_content_sync_states"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "accepted_policy_id"],
            [
                "koinon_content_policies.tenant_id",
                "koinon_content_policies.mapping_id",
                "koinon_content_policies.id",
            ],
        ),
        Index(
            "ix_content_sync_due",
            "next_run_at",
            "tenant_id",
            "mapping_id",
            postgresql_where=text("enabled AND next_run_at IS NOT NULL"),
        ),
        Index(
            "ix_content_scheduler_fair",
            text("scheduler_last_attempt_at NULLS FIRST"),
            "next_run_at",
            "tenant_id",
            "mapping_id",
            postgresql_where=text("enabled AND next_run_at IS NOT NULL"),
        ).ddl_if(dialect="postgresql"),
        CheckConstraint("scheduler_failure_count>=0", name="ck_content_scheduler_failure"),
        CheckConstraint("scan_observed_count>=0", name="ck_content_scan_count"),
        CheckConstraint("scan_max_items BETWEEN 100 AND 1000000", name="ck_content_scan_max"),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "scheduler_claim_policy_id"],
            [
                "koinon_content_policies.tenant_id",
                "koinon_content_policies.mapping_id",
                "koinon_content_policies.id",
            ],
            name="fk_content_scheduler_policy",
        ),
    )
    mapping_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_mappings.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    accepted_policy_id: Mapped[str] = mapped_column(String(64))
    enabled: Mapped[bool] = mapped_column(default=False)
    revision: Mapped[int] = mapped_column(default=1)
    next_run_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    cursor_ciphertext: Mapped[bytes | None]
    scan_generation: Mapped[int] = mapped_column(default=0)
    last_complete_scan_generation: Mapped[int] = mapped_column(default=0)
    scan_observed_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    scan_max_items: Mapped[int | None]
    scheduler_last_attempt_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    scheduler_retry_not_before: Mapped[datetime | None] = mapped_column(UtcDateTime())
    scheduler_claim_token: Mapped[UUID | None] = mapped_column(Uuid)
    scheduler_claim_until: Mapped[datetime | None] = mapped_column(UtcDateTime())
    scheduler_claim_policy_id: Mapped[str | None] = mapped_column(String(64))
    scheduler_claim_control_revision: Mapped[int | None]
    scheduler_claim_occurrence_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    scheduler_failure_count: Mapped[int] = mapped_column(default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceControlOperation(Base):
    """Immutable, replayable control receipt; execution belongs to canonical Jobs."""

    __tablename__ = "koinon_content_control_operations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "owner", "mapping_id"],
            [
                "koinon_content_mappings.tenant_id",
                "koinon_content_mappings.owner",
                "koinon_content_mappings.id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "target_run_id"],
            [
                "koinon_content_sync_runs.tenant_id",
                "koinon_content_sync_runs.mapping_id",
                "koinon_content_sync_runs.id",
            ],
            name="fk_content_control_run",
            use_alter=True,
        ),
        UniqueConstraint("tenant_id", "owner", "operation_id", name="uq_content_control_operation"),
        UniqueConstraint("tenant_id", "mapping_id", "id", name="uq_content_control_identity"),
        UniqueConstraint("tenant_id", "mapping_id", "result_revision", name="uq_content_control_revision"),
        Index(
            "ix_content_control_run",
            "tenant_id",
            "mapping_id",
            "target_run_id",
            postgresql_where=text("target_run_id IS NOT NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    owner: Mapped[str] = mapped_column(String(512))
    operation_id: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(32))
    mapping_id: Mapped[str] = mapped_column(String(64))
    target_run_id: Mapped[str | None] = mapped_column(String(64))
    expected_revision: Mapped[int]
    result_revision: Mapped[int]
    payload_sha256: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceSyncRun(Base):
    __tablename__ = "koinon_content_sync_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "policy_id"],
            [
                "koinon_content_policies.tenant_id",
                "koinon_content_policies.mapping_id",
                "koinon_content_policies.id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "cancel_operation_id"],
            [
                "koinon_content_control_operations.tenant_id",
                "koinon_content_control_operations.mapping_id",
                "koinon_content_control_operations.id",
            ],
            name="fk_content_run_cancel",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "retry_of_run_id"],
            [
                "koinon_content_sync_runs.tenant_id",
                "koinon_content_sync_runs.mapping_id",
                "koinon_content_sync_runs.id",
            ],
            name="fk_content_run_retry",
        ),
        Index(
            "ix_content_run_retry",
            "tenant_id",
            "mapping_id",
            "retry_of_run_id",
            postgresql_where=text("retry_of_run_id IS NOT NULL"),
        ),
        UniqueConstraint("tenant_id", "mapping_id", "id", name="uq_content_run_identity"),
        UniqueConstraint("tenant_id", "mapping_id", "operation_id", name="uq_content_run_operation"),
        UniqueConstraint("tenant_id", "mapping_id", "occurrence_key", name="uq_content_run_occurrence"),
        Index(
            "uq_content_run_active",
            "tenant_id",
            "mapping_id",
            unique=True,
            postgresql_where=text("status IN ('queued','running','reconciling')"),
        ),
        Index("ix_content_run_history", "tenant_id", "mapping_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    mapping_id: Mapped[str] = mapped_column(String(64))
    policy_id: Mapped[str] = mapped_column(String(64))
    mapping_revision: Mapped[int]
    connection_revision: Mapped[int]
    job_id: Mapped[str] = mapped_column(ForeignKey("lattice_jobs.id"), unique=True)
    trigger_kind: Mapped[str] = mapped_column(String(32))
    operation_id: Mapped[str] = mapped_column(String(64))
    payload_sha256: Mapped[str] = mapped_column(String(64))
    occurrence_key: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), default="queued")
    page_sequence: Mapped[int] = mapped_column(default=0)
    cursor_ciphertext: Mapped[bytes | None]
    scan_generation: Mapped[int]
    enumeration_complete: Mapped[bool] = mapped_column(default=False)
    counters_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    finished_at: Mapped[datetime | None] = mapped_column(UtcDateTime())
    cancel_requested_at: Mapped[datetime | None] = mapped_column(UtcDateTime(), default=None)
    cancel_operation_id: Mapped[str | None] = mapped_column(String(64), default=None)
    retry_of_run_id: Mapped[str | None] = mapped_column(String(64), default=None)


class SourceSyncWork(Base):
    __tablename__ = "koinon_content_sync_work"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "object_id"],
            [
                "koinon_content_objects.tenant_id",
                "koinon_content_objects.mapping_id",
                "koinon_content_objects.id",
            ],
        ),
        UniqueConstraint(
            "tenant_id", "mapping_id", "object_id", "generation", name="uq_content_work_generation"
        ),
        UniqueConstraint(
            "tenant_id", "mapping_id", "object_id", "generation", "id", name="uq_content_work_identity"
        ),
        Index("ix_content_work_pending", "tenant_id", "mapping_id", "status", "id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    mapping_id: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str] = mapped_column(String(64))
    generation: Mapped[int]
    remote_version: Mapped[str | None] = mapped_column(String(2048))
    event_sha256: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="admitted")
    error_code: Mapped[str | None] = mapped_column(String(64))
    attempt_id: Mapped[str | None] = mapped_column(ForeignKey("koinon_content_imports.id"))
    expected_local_revision: Mapped[str | None] = mapped_column(String(128))
    expected_sha256: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceSyncObservation(Base):
    __tablename__ = "koinon_content_sync_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "run_id"],
            [
                "koinon_content_sync_runs.tenant_id",
                "koinon_content_sync_runs.mapping_id",
                "koinon_content_sync_runs.id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "object_id", "generation", "work_id"],
            [
                "koinon_content_sync_work.tenant_id",
                "koinon_content_sync_work.mapping_id",
                "koinon_content_sync_work.object_id",
                "koinon_content_sync_work.generation",
                "koinon_content_sync_work.id",
            ],
        ),
        UniqueConstraint("run_id", "page_sequence", "item_sequence", name="uq_content_observation_position"),
        UniqueConstraint(
            "tenant_id", "mapping_id", "object_id", "work_id", "id", name="uq_content_observation_publication"
        ),
        Index("ix_content_observation_work", "work_id"),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    mapping_id: Mapped[str] = mapped_column(String(64))
    run_id: Mapped[str] = mapped_column(String(64))
    page_sequence: Mapped[int]
    item_sequence: Mapped[int]
    object_id: Mapped[str] = mapped_column(String(64))
    generation: Mapped[int]
    remote_version: Mapped[str | None] = mapped_column(String(2048))
    event_json: Mapped[dict] = mapped_column(JSON)
    event_sha256: Mapped[str] = mapped_column(String(64))
    work_id: Mapped[str] = mapped_column(String(64))
    observed_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceFolderBinding(Base):
    __tablename__ = "koinon_content_folder_bindings"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id"], ["koinon_content_mappings.tenant_id", "koinon_content_mappings.id"]
        ),
        Index("ix_content_folder_local", "local_folder_id"),
    )
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    mapping_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    remote_folder_id: Mapped[str] = mapped_column(String(1024), primary_key=True)
    local_folder_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"))
    remote_parent_id: Mapped[str | None] = mapped_column(String(1024))
    local_parent_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"))
    ancestry_json: Mapped[list[str]] = mapped_column(JSON)
    revision: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceFolderPublication(Base):
    """Retained exact source observation for one canonical folder publication."""

    __tablename__ = "koinon_content_folder_publications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "object_id"],
            [
                "koinon_content_objects.tenant_id",
                "koinon_content_objects.mapping_id",
                "koinon_content_objects.id",
            ],
        ),
        ForeignKeyConstraint(
            ["tenant_id", "mapping_id", "object_id", "work_id", "observation_id"],
            [
                "koinon_content_sync_observations.tenant_id",
                "koinon_content_sync_observations.mapping_id",
                "koinon_content_sync_observations.object_id",
                "koinon_content_sync_observations.work_id",
                "koinon_content_sync_observations.id",
            ],
        ),
        UniqueConstraint(
            "tenant_id", "mapping_id", "object_id", "observation_id", name="uq_content_folder_observation"
        ),
        UniqueConstraint("local_folder_id", "canonical_revision", name="uq_content_folder_revision"),
        UniqueConstraint("previous_publication_id", name="uq_content_folder_successor"),
        CheckConstraint("canonical_revision>0", name="ck_content_folder_revision"),
        Index("ix_content_folder_publication_history", "tenant_id", "local_folder_id", "canonical_revision"),
        Index("ix_content_folder_publication_parent", "local_parent_id"),
        Index("ix_content_folder_publication_observation", "observation_id"),
        Index("ix_content_folder_publication_work", "work_id"),
        Index(
            "uq_content_folder_initial",
            "local_folder_id",
            unique=True,
            postgresql_where=text("previous_publication_id IS NULL"),
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    mapping_id: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str] = mapped_column(String(64))
    observation_id: Mapped[str] = mapped_column(String(64))
    work_id: Mapped[str] = mapped_column(String(64))
    local_folder_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"))
    local_parent_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"))
    canonical_revision: Mapped[int] = mapped_column(BigInteger)
    canonical_sha256: Mapped[str] = mapped_column(String(64))
    previous_publication_id: Mapped[str | None] = mapped_column(
        ForeignKey("koinon_content_folder_publications.id")
    )
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceImportedAsset(Base):
    __tablename__ = "koinon_content_imported_assets"
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_id", "asset_id", name="uq_content_imported_asset_identity"),
        Index("ix_content_imported_source", "tenant_id", "source_id"),
    )
    asset_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"))
    source_id: Mapped[str] = mapped_column(ForeignKey("lattice_catalog.id"))
    initial_attempt_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_imports.id"), unique=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourceImportedVersion(Base):
    __tablename__ = "koinon_content_imported_versions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "source_id", "asset_id"],
            [
                "koinon_content_imported_assets.tenant_id",
                "koinon_content_imported_assets.source_id",
                "koinon_content_imported_assets.asset_id",
            ],
        ),
        UniqueConstraint(
            "tenant_id",
            "domain",
            "native_workspace_id",
            "native_asset_id",
            "native_version_id",
            name="uq_content_imported_native_version",
        ),
        Index("ix_content_imported_version_asset", "tenant_id", "asset_id", "created_at"),
        CheckConstraint("domain IN ('canon','structured')", name="ck_content_imported_domain"),
    )
    attempt_id: Mapped[str] = mapped_column(ForeignKey("koinon_content_imports.id"), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    source_id: Mapped[str] = mapped_column(String(64))
    asset_id: Mapped[str] = mapped_column(String(64))
    domain: Mapped[str] = mapped_column(String(32))
    native_workspace_id: Mapped[str] = mapped_column(String(64))
    native_source_id: Mapped[str] = mapped_column(String(64))
    native_asset_id: Mapped[str] = mapped_column(String(64))
    native_version_id: Mapped[str] = mapped_column(String(64))
    extraction_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))
