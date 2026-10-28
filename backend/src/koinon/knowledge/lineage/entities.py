# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product-owned immutable metadata in the structured datasource."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from flyquery.models.entities import Base
from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column


def now():
    return datetime.now(UTC)


class Scoped:
    tenant_id: Mapped[str] = mapped_column(String(512))
    workspace_id: Mapped[UUID] = mapped_column(Uuid)
    dataset_id: Mapped[UUID] = mapped_column(Uuid)
    actor: Mapped[str] = mapped_column(String(512))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class SourceArtifactRow(Scoped, Base):
    __tablename__ = "flyquery_lineage_artifacts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    original_filename: Mapped[str] = mapped_column(String(512))
    sha256: Mapped[str] = mapped_column(String(64))
    byte_size: Mapped[int] = mapped_column(BigInteger)
    file_format: Mapped[str] = mapped_column(String(32))
    compression: Mapped[str] = mapped_column(String(32))


class TransformRunRow(Scoped, Base):
    __tablename__ = "flyquery_lineage_runs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    artifact_id: Mapped[UUID] = mapped_column(Uuid)
    operation: Mapped[str] = mapped_column(String(16))
    predecessor_snapshot_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    sheet_or_json_path: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    table_label: Mapped[str] = mapped_column(String(512))
    implementation: Mapped[str] = mapped_column(String(512))
    implementation_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON)


class TransformStepRow(Scoped, Base):
    __tablename__ = "flyquery_lineage_steps"
    __table_args__ = (UniqueConstraint("run_id", "ordinal", name="uq_lineage_step_order"),)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    run_id: Mapped[UUID] = mapped_column(Uuid)
    ordinal: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(32))
    implementation: Mapped[str] = mapped_column(String(512))
    implementation_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    parameters: Mapped[dict] = mapped_column(JSON)


class SnapshotLineageRow(Scoped, Base):
    __tablename__ = "flyquery_snapshot_lineage"
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(Uuid, unique=True)
    table_id: Mapped[UUID] = mapped_column(Uuid)
    parquet_sha256: Mapped[str] = mapped_column(String(64))
    parquet_byte_size: Mapped[int] = mapped_column(BigInteger)
    schema_sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(BigInteger)
