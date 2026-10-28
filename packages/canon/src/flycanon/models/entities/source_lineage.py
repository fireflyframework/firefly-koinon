# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Product-only lineage, deliberately outside standalone Base.metadata."""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKeyConstraint,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)

metadata = MetaData()


def scoped():
    return [
        Column("tenant_id", String(64), nullable=False),
        Column("workspace_id", String(64), nullable=False),
        Column("source_id", String(36), nullable=False),
    ]


def immutable(name, *columns, constraints=()):
    return Table(
        name,
        metadata,
        Column("id", String(36), primary_key=True),
        *scoped(),
        *columns,
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        UniqueConstraint("id", "tenant_id", "workspace_id", "source_id"),
        *constraints,
    )


source_artifacts = immutable(
    "canon_source_artifacts",
    Column("role", String(32), nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("bytes", Integer, nullable=False),
    Column("media_type", String(128)),
    Column("object_key", String(1024), nullable=False),
)
source_versions = immutable(
    "canon_source_versions",
    Column("artifact_id", String(36), nullable=False),
    Column("logical_key", String(128), nullable=False),
    Column("operation_id", String(128), nullable=False),
    Column("filename", String(512)),
    Column("media_type", String(128)),
    Column("actor", Text),
    Column("predecessor_id", String(36)),
    Column("expected_extraction_id", String(36)),
    constraints=(UniqueConstraint("tenant_id", "workspace_id", "operation_id"),),
)
source_extractions = immutable(
    "canon_source_extractions",
    Column("version_id", String(36), nullable=False),
    Column("purpose", String(32), nullable=False),
    Column("normalized_artifact_id", String(36), nullable=False),
    Column("predecessor_id", String(36)),
    Column("implementation", JSON, nullable=False),
    Column("coverage", String(32), nullable=False),
    Column("projection", JSON, nullable=False),
)
source_parts = immutable(
    "canon_source_parts",
    Column("extraction_id", String(36), nullable=False),
    Column("artifact_id", String(36)),
    Column("kind", String(32), nullable=False),
    Column("parent_id", String(36)),
    Column("ordinal", Integer, nullable=False),
    Column("text", Text, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("page", Integer),
    Column("section_path", JSON),
    Column("char_start", Integer),
    Column("char_end", Integer),
    Column("offset_basis", String(64)),
    Column("projection_chunk_id", String(36)),
)
source_steps = immutable(
    "canon_source_transform_steps",
    Column("extraction_id", String(36), nullable=False),
    Column("ordinal", Integer, nullable=False),
    Column("stage", String(64), nullable=False),
    Column("input_artifact_id", String(36), nullable=False),
    Column("output_artifact_id", String(36), nullable=False),
    Column("implementation", JSON, nullable=False),
    Column("parameters", JSON, nullable=False),
)
source_events = immutable(
    "canon_source_lineage_events",
    Column("version_id", String(36), nullable=False),
    Column("extraction_id", String(36)),
    Column("status", String(32), nullable=False),
    Column("reason_code", String(64)),
)
source_heads = Table(
    "canon_source_heads",
    metadata,
    *scoped(),
    Column("logical_key", String(128), nullable=False),
    Column("version_id", String(36)),
    Column("extraction_id", String(36)),
    UniqueConstraint("tenant_id", "workspace_id", "source_id"),
    UniqueConstraint("tenant_id", "workspace_id", "logical_key"),
)


def reference(child, column, parent):
    scope = ["tenant_id", "workspace_id", "source_id"]
    child.append_constraint(
        ForeignKeyConstraint([column, *scope], [f"{parent.name}.{name}" for name in ["id", *scope]])
    )


reference(source_versions, "artifact_id", source_artifacts)
reference(source_versions, "predecessor_id", source_versions)
reference(source_versions, "expected_extraction_id", source_extractions)
reference(source_extractions, "version_id", source_versions)
reference(source_extractions, "normalized_artifact_id", source_artifacts)
reference(source_extractions, "predecessor_id", source_extractions)
reference(source_parts, "extraction_id", source_extractions)
reference(source_parts, "artifact_id", source_artifacts)
reference(source_parts, "parent_id", source_parts)
reference(source_steps, "extraction_id", source_extractions)
reference(source_steps, "input_artifact_id", source_artifacts)
reference(source_steps, "output_artifact_id", source_artifacts)
reference(source_events, "version_id", source_versions)
reference(source_events, "extraction_id", source_extractions)
reference(source_heads, "version_id", source_versions)
reference(source_heads, "extraction_id", source_extractions)
