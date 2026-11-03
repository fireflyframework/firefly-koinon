# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Short native readiness snapshots and held fences for a previously verified corpus."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

from pyfly.data.transaction import Propagation, TransactionTemplate
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from flycanon.models.repositories.source_repository import SourceRepository


@dataclass(frozen=True, slots=True)
class ReadinessSnapshot:
    tenant_generation: int


@dataclass(frozen=True, slots=True)
class ReadinessChange:
    generation: int
    workspace_id: str


class ReadinessGenerationChangedError(RuntimeError):
    """The verified snapshot no longer describes the committed native corpus."""


class ReadinessGenerationRepository:
    def __init__(self, sources: SourceRepository):
        self.sources = sources

    @asynccontextmanager
    async def _unit(self, tenant_id: str) -> AsyncIterator[AsyncSession]:
        if not tenant_id:
            raise ValueError("A native tenant is required")
        async with TransactionTemplate(
            self.sources.session_factory, propagation=Propagation.REQUIRES_NEW
        ).transaction() as unit:
            if unit is None:
                raise RuntimeError("Native readiness requires a database transaction")
            session: AsyncSession = unit.resource
            await session.execute(
                text("SELECT set_config('app.tenant_id',:tenant,true)"), {"tenant": tenant_id}
            )
            yield session

    async def snapshot(self, tenant_id: str) -> ReadinessSnapshot:
        async with self._unit(tenant_id) as session:
            await session.execute(
                text("SELECT public.koinon_ensure_canon_readiness(:tenant)"), {"tenant": tenant_id}
            )
            generation = await session.scalar(
                text("SELECT generation FROM public.canon_readiness_generations WHERE tenant_id=:tenant"),
                {"tenant": tenant_id},
            )
            if generation is None:
                raise ReadinessGenerationChangedError("Native readiness generation is unavailable")
            return ReadinessSnapshot(int(generation))

    async def changes(
        self,
        tenant_id: str,
        *,
        after_generation: int,
        after_workspace_id: str | None = None,
        limit: int = 100,
    ) -> list[ReadinessChange]:
        if after_generation < 0 or not 1 <= limit <= 100:
            raise ValueError("Readiness changes require a nonnegative cursor and a limit from 1 to 100")
        async with self._unit(tenant_id) as session:
            rows = await session.execute(
                text(
                    "SELECT generation,workspace_id FROM public.canon_readiness_changes "
                    "WHERE tenant_id=:tenant AND (generation>:generation OR "
                    "(CAST(:workspace AS text) IS NOT NULL AND generation=:generation AND "
                    "workspace_id>:workspace)) "
                    "ORDER BY generation,workspace_id LIMIT :limit"
                ),
                {
                    "tenant": tenant_id,
                    "generation": after_generation,
                    "workspace": after_workspace_id,
                    "limit": limit,
                },
            )
            return [ReadinessChange(int(row.generation), str(row.workspace_id)) for row in rows]

    @asynccontextmanager
    async def hold(self, tenant_id: str, expected: ReadinessSnapshot) -> AsyncIterator[None]:
        """Keep native writers fenced until the caller has committed its primary CAS."""
        async with self._unit(tenant_id) as session:
            generation = await session.scalar(
                text(
                    "SELECT generation FROM public.canon_readiness_generations "
                    "WHERE tenant_id=:tenant FOR SHARE"
                ),
                {"tenant": tenant_id},
            )
            if generation is None or int(generation) != expected.tenant_generation:
                raise ReadinessGenerationChangedError("Native knowledge changed after readiness verification")
            yield
