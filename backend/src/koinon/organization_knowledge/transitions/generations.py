# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read-only consumption of database-owned authority and corpus change generations."""

from dataclasses import dataclass

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Base, Repository
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    and_,
    event,
    or_,
    select,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from koinon.organization_knowledge.transitions import generation_schema_v1 as generation_schema


class KnowledgeReadinessGeneration(Base):
    __tablename__ = generation_schema.GENERATIONS
    __table_args__ = (CheckConstraint("generation >= 0", name="ck_knowledge_readiness_generation"),)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey("lattice_tenants.id", ondelete="CASCADE"), primary_key=True
    )
    generation: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    fence: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_transaction: Mapped[str | None] = mapped_column(
        String(32).with_variant(generation_schema.TransactionId(), "postgresql"), nullable=True
    )


class KnowledgeReadinessChange(Base):
    __tablename__ = generation_schema.CHANGES
    __table_args__ = (Index("ix_knowledge_readiness_changes", "tenant_id", "generation", "workspace_id"),)
    tenant_id: Mapped[str] = mapped_column(
        ForeignKey(generation_schema.GENERATIONS + ".tenant_id", ondelete="CASCADE"), primary_key=True
    )
    workspace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    generation: Mapped[int] = mapped_column(BigInteger)


def install_on_create(_metadata, connection, **_kwargs):
    generation_schema.install(connection)


event.listen(Base.metadata, "after_create", install_on_create)


@dataclass(frozen=True)
class ReadinessChange:
    generation: int
    workspace_id: str


@repository(name="organization_knowledge.mode_generations")
class ModeGenerationRepository(Repository[KnowledgeReadinessGeneration, str]):
    async def matches(self, tenant_id, expected):
        session = self._require_session()
        if session.get_bind().dialect.name == "postgresql":
            return (
                await session.scalar(
                    text("SELECT public.koinon_lock_knowledge_readiness(:tenant,:expected)"),
                    {"tenant": tenant_id, "expected": expected},
                )
                is True
            )
        return await self.current(tenant_id, lock=True) == expected

    async def current(self, tenant_id, *, lock=False):
        statement = select(KnowledgeReadinessGeneration.generation).where(
            KnowledgeReadinessGeneration.tenant_id == tenant_id
        )
        if lock:
            statement = statement.with_for_update(read=True)
        value = await self._require_session().scalar(statement)
        if type(value) is not int or value < 0:
            raise ServiceUnavailableException(
                "The durable readiness generation is unavailable",
                code="KNOWLEDGE_MODE_GENERATION_UNAVAILABLE",
            )
        return value

    async def changes(self, tenant_id, *, after_generation, after_workspace_id=None, limit=100):
        if (
            type(limit) is not int
            or not 1 <= limit <= 100
            or type(after_generation) is not int
            or after_generation < 0
        ):
            raise ValueError("Readiness changes require a nonnegative generation and page from 1 to 100")
        row = KnowledgeReadinessChange
        cursor = row.generation > after_generation
        if after_workspace_id is not None:
            cursor = or_(
                cursor, and_(row.generation == after_generation, row.workspace_id > after_workspace_id)
            )
        values = await self._require_session().execute(
            select(row.generation, row.workspace_id)
            .where(
                row.tenant_id == tenant_id,
                cursor,
            )
            .order_by(row.generation, row.workspace_id)
            .limit(limit)
        )
        return [ReadinessChange(value.generation, value.workspace_id) for value in values]
