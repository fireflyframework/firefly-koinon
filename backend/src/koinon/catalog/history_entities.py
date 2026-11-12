# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Database-owned retained identities and typed audit dependencies."""

from pyfly.data.relational.sqlalchemy import Base
from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import Mapped, mapped_column

from koinon.catalog.history_guards import install_on_create
from koinon.organization_knowledge.transitions.generation_schema_v1 import TransactionId


class RetainedTransactionId(TransactionId):
    """Normalize psycopg text and asyncpg integer xid8 results without changing SQL storage."""

    cache_ok = True

    def result_processor(self, dialect, coltype):
        return lambda value: None if value is None else int(value)


class CatalogHistoryIdentity(Base):
    __tablename__ = "koinon_catalog_history_identities"
    __table_args__ = (
        UniqueConstraint("resource_id", name="uq_catalog_history_resource"),
        CheckConstraint("coverage IN ('complete','legacy_unknown')", name="ck_catalog_history_coverage"),
    )
    tenant_id: Mapped[str] = mapped_column(ForeignKey("lattice_tenants.id"), primary_key=True)
    resource_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    coverage: Mapped[str] = mapped_column(String(32))
    creation_transaction: Mapped[int | None] = mapped_column(RetainedTransactionId(), nullable=True)


class CatalogHistoryEdge(Base):
    __tablename__ = "koinon_catalog_history_edges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "dependent_id"],
            ["koinon_catalog_history_identities.tenant_id", "koinon_catalog_history_identities.resource_id"],
            name="fk_catalog_history_dependent",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "origin_id"],
            ["koinon_catalog_history_identities.tenant_id", "koinon_catalog_history_identities.resource_id"],
            name="fk_catalog_history_origin",
        ),
        CheckConstraint("kind IN ('parent','curated_source')", name="ck_catalog_history_kind"),
        Index("ix_catalog_history_origin", "tenant_id", "origin_id", "dependent_id"),
    )
    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dependent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    origin_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), primary_key=True)


event.listen(Base.metadata, "after_create", install_on_create)
