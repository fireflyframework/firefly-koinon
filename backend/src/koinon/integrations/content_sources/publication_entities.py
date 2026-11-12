# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained canonical publication baselines; never a source authorization grant."""

from datetime import UTC, datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.history_entities import RetainedTransactionId


class SourcePublicationBaseline(Base):
    __tablename__ = "koinon_content_publication_baselines"
    __table_args__ = (
        UniqueConstraint("attempt_id", "tenant_id", name="uq_content_publication_scope"),
        Index("ix_content_publication_object", "tenant_id", "object_id", "attempt_id"),
        Index("ix_content_publication_previous", "previous_attempt_id"),
        Index("ix_content_publication_mapping", "mapping_id"),
        Index("ix_content_publication_object_fk", "object_id"),
        Index("ix_content_publication_structure", "previous_structure_publication_id"),
        Index("ix_content_publication_ack", "tenant_id", "mapping_id", "object_id", "acknowledgement_sha256"),
        ForeignKeyConstraint(
            [
                "previous_structure_publication_id",
                "tenant_id",
                "mapping_id",
                "object_id",
                "previous_attempt_id",
            ],
            [
                "koinon_content_structure_publications.id",
                "koinon_content_structure_publications.tenant_id",
                "koinon_content_structure_publications.mapping_id",
                "koinon_content_structure_publications.object_id",
                "koinon_content_structure_publications.content_attempt_id",
            ],
            name="fk_content_publication_structure",
            use_alter=True,
        ),
        CheckConstraint(
            "producer_kind IN ('initial_document','initial_dataset','replace_document','replace_dataset')",
            name="ck_content_publication_producer",
        ),
    )
    attempt_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("koinon_content_imports.id"), primary_key=True
    )
    tenant_id: Mapped[str] = mapped_column(String(64), ForeignKey("lattice_tenants.id"))
    workspace_id: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str] = mapped_column(String(64))
    mapping_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_content_mappings.id"))
    object_id: Mapped[str] = mapped_column(String(64), ForeignKey("koinon_content_objects.id"))
    source_id: Mapped[str] = mapped_column(String(64))
    asset_id: Mapped[str] = mapped_column(String(64))
    producer_kind: Mapped[str] = mapped_column(String(32))
    previous_attempt_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("koinon_content_publication_baselines.attempt_id"), nullable=True
    )
    descriptor_json: Mapped[dict | None] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True
    )
    descriptor_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous_structure_publication_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    acknowledgement_json: Mapped[dict | None] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql"), nullable=True
    )
    acknowledgement_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime(), default=lambda: datetime.now(UTC))


class SourcePublicationTarget(Base):
    __tablename__ = "koinon_content_publication_targets"
    __table_args__ = (
        ForeignKeyConstraint(
            ["attempt_id", "tenant_id"],
            [
                "koinon_content_publication_baselines.attempt_id",
                "koinon_content_publication_baselines.tenant_id",
            ],
            name="fk_content_publication_target_scope",
        ),
        CheckConstraint(
            "role IN ('source','asset','old_index','new_index','member')", name="ck_content_publication_role"
        ),
        CheckConstraint(
            "disposition IN ('retain','add','remove')", name="ck_content_publication_disposition"
        ),
        CheckConstraint("mutation_revision > 0", name="ck_content_publication_revision"),
    )
    attempt_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    catalog_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    workspace_id: Mapped[str] = mapped_column(String(64))
    project_id: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(16))
    disposition: Mapped[str] = mapped_column(String(16))
    parent_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    mutation_revision: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(32))
    native_domain: Mapped[str | None] = mapped_column(String(32), nullable=True)
    native_workspace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    native_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    native_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    native_snapshot_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class SourcePublicationTransaction(Base):
    """Private database-owned proof of one complete canonical publication transaction."""

    __tablename__ = "koinon_content_publication_transactions"
    __table_args__ = (Index("ix_content_publication_transaction", "transaction_id", "attempt_id"),)
    attempt_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("koinon_content_publication_baselines.attempt_id"), primary_key=True
    )
    transaction_id: Mapped[int] = mapped_column(RetainedTransactionId())
    native_receipt: Mapped[dict] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
    )
    write_counts: Mapped[dict] = mapped_column(
        JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")
    )
    closed: Mapped[bool] = mapped_column(Boolean)


from koinon.integrations.content_sources import (  # noqa: E402
    structure_publication_entities as structure_publication_entities,
)
