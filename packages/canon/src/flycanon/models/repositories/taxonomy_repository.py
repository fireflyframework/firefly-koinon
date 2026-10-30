# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Async repository for :class:`TaxonomyNodeRow`."""

from __future__ import annotations

from contextlib import asynccontextmanager

from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from flycanon.models.entities.taxonomy_node import TaxonomyNodeRow
from flycanon.models.repositories._engine import build_session_factory


class TaxonomyRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        engine: AsyncEngine | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._engine = engine

    @property
    def engine(self) -> AsyncEngine | None:
        return self._engine

    @classmethod
    def from_url(
        cls,
        database_url: str,
        *,
        echo: bool = False,
        registry: DataSourceRegistry | None = None,
        datasource_name: str = "canon",
    ) -> TaxonomyRepository:
        factory, engine = build_session_factory(
            database_url, echo=echo, registry=registry, datasource_name=datasource_name
        )
        return cls(factory, engine=engine)

    @asynccontextmanager
    async def session(self):
        async with infrastructure_unit(self._session_factory) as session:
            yield session

    async def get(self, node_id: str, *, tenant_id=None, workspace_id=None) -> TaxonomyNodeRow | None:
        async with infrastructure_unit(self._session_factory) as session:
            statement = select(TaxonomyNodeRow).where(TaxonomyNodeRow.id == node_id)
            if tenant_id is not None:
                statement = statement.where(TaxonomyNodeRow.tenant_id == tenant_id)
            if workspace_id is not None:
                statement = statement.where(TaxonomyNodeRow.workspace_id == workspace_id)
            return (await session.execute(statement)).scalars().first()

    async def list_all(self, *, tenant_id=None, workspace_id=None) -> list[TaxonomyNodeRow]:
        async with infrastructure_unit(self._session_factory) as session:
            statement = select(TaxonomyNodeRow)
            if tenant_id is not None:
                statement = statement.where(TaxonomyNodeRow.tenant_id == tenant_id)
            if workspace_id is not None:
                statement = statement.where(TaxonomyNodeRow.workspace_id == workspace_id)
            result = await session.execute(
                statement.order_by(TaxonomyNodeRow.depth.asc(), TaxonomyNodeRow.label.asc())
            )
            return list(result.scalars().all())

    async def add(self, row: TaxonomyNodeRow) -> TaxonomyNodeRow:
        async with self.session() as session:
            session.add(row)
            await session.flush()
            await session.refresh(row)
            return row
