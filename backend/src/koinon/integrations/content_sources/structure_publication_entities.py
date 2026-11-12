# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable file structure transitions anchored to retained content evidence."""

from datetime import datetime

from pyfly.data.relational.sqlalchemy import Base, UtcDateTime
from sqlalchemy import JSON, CheckConstraint, ForeignKeyConstraint, Index, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.history_entities import RetainedTransactionId
from koinon.integrations.content_sources import publication_entities as publication_entities
from koinon.integrations.content_sources import sync_entities as sync_entities


class SourceStructurePublication(Base):
    __tablename__ = "koinon_content_structure_publications"
    __table_args__ = (
        ForeignKeyConstraint(
            ["content_attempt_id", "tenant_id"],
            [
                "koinon_content_publication_baselines.attempt_id",
                "koinon_content_publication_baselines.tenant_id",
            ],
            name="fk_structure_content_scope",
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
            name="fk_structure_observation_scope",
        ),
        UniqueConstraint(
            "id",
            "tenant_id",
            "mapping_id",
            "object_id",
            "content_attempt_id",
            name="uq_structure_anchor_scope",
        ),
        ForeignKeyConstraint(
            ["previous_publication_id", "tenant_id", "mapping_id", "object_id", "content_attempt_id"],
            [
                "koinon_content_structure_publications.id",
                "koinon_content_structure_publications.tenant_id",
                "koinon_content_structure_publications.mapping_id",
                "koinon_content_structure_publications.object_id",
                "koinon_content_structure_publications.content_attempt_id",
            ],
            name="fk_structure_predecessor_scope",
        ),
        UniqueConstraint("proof_sha256", name="uq_structure_digest"),
        UniqueConstraint("work_id", "observation_id", name="uq_structure_observation"),
        UniqueConstraint("previous_publication_id", name="uq_structure_successor"),
        Index(
            "uq_structure_first",
            "content_attempt_id",
            unique=True,
            postgresql_where=text("previous_publication_id IS NULL"),
            sqlite_where=text("previous_publication_id IS NULL"),
        ),
        Index("uq_structure_transaction_object", "transaction_id", "object_id", unique=True),
        Index("ix_structure_object", "tenant_id", "mapping_id", "object_id", "content_attempt_id"),
        CheckConstraint("length(proof_sha256)=64", name="ck_structure_digest"),
        CheckConstraint("octet_length(payload_json::text)<=262144", name="ck_structure_payload").ddl_if(
            dialect="postgresql"
        ),
    )
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(64))
    mapping_id: Mapped[str] = mapped_column(String(64))
    object_id: Mapped[str] = mapped_column(String(64))
    content_attempt_id: Mapped[str] = mapped_column(String(64))
    previous_publication_id: Mapped[str | None] = mapped_column(String(64))
    work_id: Mapped[str] = mapped_column(String(64))
    observation_id: Mapped[str] = mapped_column(String(64))
    transaction_id: Mapped[int] = mapped_column(RetainedTransactionId())
    proof_sha256: Mapped[str] = mapped_column(String(64))
    payload_json: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    created_at: Mapped[datetime] = mapped_column(UtcDateTime())
