# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import UUID

from flyquery.models.entities import Base
from sqlalchemy import JSON, BigInteger, Boolean, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from koinon.knowledge.lineage.entities import Scoped


class CoordinateManifestRow(Scoped, Base):
    __tablename__ = "flyquery_coordinate_manifests"
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    table_id: Mapped[UUID] = mapped_column(Uuid)
    run_id: Mapped[UUID] = mapped_column(Uuid)
    artifact_id: Mapped[UUID] = mapped_column(Uuid)
    input_sha256: Mapped[str] = mapped_column(String(64))
    mapping_sha256: Mapped[str] = mapped_column(String(64))
    row_count: Mapped[int] = mapped_column(BigInteger)
    column_count: Mapped[int] = mapped_column(Integer)
    complete: Mapped[bool] = mapped_column(Boolean)
    reason_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    descriptor: Mapped[dict] = mapped_column(JSON)


class CoordinateRangeRow(Scoped, Base):
    __tablename__ = "flyquery_coordinate_ranges"
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    output_start: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    count: Mapped[int] = mapped_column(BigInteger)
    source_start: Mapped[int] = mapped_column(BigInteger)
    source_stride: Mapped[int] = mapped_column(BigInteger)


class CoordinateColumnRow(Scoped, Base):
    __tablename__ = "flyquery_coordinate_columns"
    snapshot_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    output_position: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_field_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_path: Mapped[list] = mapped_column(JSON)
    source_type: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    header_cells: Mapped[list] = mapped_column(JSON)
