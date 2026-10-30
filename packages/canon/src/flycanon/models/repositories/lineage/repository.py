# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Application-owned native units for immutable document ledger operations."""

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import Any

from pyfly.data.transaction import Propagation, TransactionTemplate
from pyfly.kernel import ServiceUnavailableException
from sqlalchemy import and_, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.core.services.sources.lineage.ports import (
    IngestionPartQuery,
    LineageEntity,
    LineageQuery,
    LineageRecord,
)
from flycanon.models.entities.source import SourceRow
from flycanon.models.entities.source_lineage import source_events, source_extractions, source_parts
from flycanon.models.repositories.lineage.statements import TABLES, conditions, statement
from flycanon.models.repositories.source_repository import SourceRepository


class NativeLineageUnit:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def first(self, query: LineageQuery) -> LineageRecord | None:
        row = (await self._session.execute(statement(query))).mappings().first()
        return dict(row) if row is not None else None

    async def one(self, query: LineageQuery) -> LineageRecord:
        return dict((await self._session.execute(statement(query))).mappings().one())

    async def all(self, query: LineageQuery) -> Sequence[LineageRecord]:
        return [dict(row) for row in (await self._session.execute(statement(query))).mappings().all()]

    async def scalar(self, query: LineageQuery, column: str) -> Any:
        selected = statement(query).with_only_columns(TABLES[query.entity].c[column])
        return await self._session.scalar(selected)

    async def count(self, query: LineageQuery) -> int:
        selected = statement(query).with_only_columns(func.count()).select_from(TABLES[query.entity])
        return (await self._session.execute(selected)).scalar_one()

    async def source(self, query: LineageQuery) -> SourceRow | None:
        return (await self._session.execute(statement(query))).scalars().first()

    async def perform(self, query: LineageQuery) -> None:
        await self._session.execute(statement(query))

    async def insert(self, entity: LineageEntity, records: LineageRecord | Sequence[LineageRecord]) -> None:
        if isinstance(records, Mapping):
            await self._session.execute(insert(TABLES[entity]).values(**records))
        else:
            await self._session.execute(insert(TABLES[entity]), list(records))

    async def update(self, query: LineageQuery, values: LineageRecord) -> None:
        where = statement(query).whereclause
        if where is None:
            raise ValueError("A scoped lineage update is required")
        await self._session.execute(update(TABLES[query.entity]).where(where).values(**values))

    def add_source(self, source: SourceRow) -> None:
        self._session.add(source)


class NativeLineageRepository:
    def __init__(self, source_repository: SourceRepository):
        self.sources = source_repository

    @asynccontextmanager
    async def read(self) -> AsyncIterator[NativeLineageUnit]:
        async with self.sources.session() as session:
            yield NativeLineageUnit(session)

    @asynccontextmanager
    async def raw_write(self) -> AsyncIterator[AsyncSession]:
        async with TransactionTemplate(
            self.sources.session_factory, propagation=Propagation.REQUIRES_NEW
        ).transaction() as unit:
            if unit is None:
                raise ServiceUnavailableException(
                    "Document storage requires a native transaction", code="DOCUMENT_LINEAGE_UNAVAILABLE"
                )
            yield unit.resource

    @asynccontextmanager
    async def write(self) -> AsyncIterator[NativeLineageUnit]:
        async with self.raw_write() as session:
            yield NativeLineageUnit(session)

    async def require_schema(self) -> None:
        async with self.sources.session() as session:
            await session.execute(select(TABLES["head"]).limit(0))

    async def ingestion_chunks(
        self, scope: DocumentScope, query: IngestionPartQuery
    ) -> Sequence[LineageRecord]:
        predicates = []
        if query.source_id is not None:
            predicates.append(source_parts.c.source_id == query.source_id)
        if query.extraction_id is not None:
            predicates.append(source_parts.c.extraction_id == query.extraction_id)
        if query.part_ids is not None:
            predicates.append(source_parts.c.id.in_(query.part_ids))
        if query.projection_chunk_ids is not None:
            predicates.append(source_parts.c.projection_chunk_id.in_(query.projection_chunk_ids))
        return await self.legacy_chunks(
            scope, *predicates, max_rows=query.max_rows, max_bytes=query.max_bytes
        )

    async def legacy_chunks(
        self, scope: DocumentScope, *predicates, max_rows=1000, max_bytes=64 * 1024 * 1024
    ) -> Sequence[LineageRecord]:
        from flycanon.models.repositories.lineage.ingestion import read_chunk_records

        return await read_chunk_records(
            self.sources, scope, *predicates, max_rows=max_rows, max_bytes=max_bytes
        )

    async def committed_sources(self, scope: DocumentScope, source_ids: Sequence[str]) -> set[str]:
        async with self.sources.session() as session:
            return set(
                (
                    await session.scalars(
                        select(source_extractions.c.source_id)
                        .join(
                            source_events,
                            and_(
                                source_events.c.extraction_id == source_extractions.c.id,
                                source_events.c.version_id == source_extractions.c.version_id,
                                *(
                                    source_events.c[key] == source_extractions.c[key]
                                    for key in ("tenant_id", "workspace_id", "source_id")
                                ),
                            ),
                        )
                        .where(
                            *conditions(source_extractions, scope),
                            source_extractions.c.purpose == "ingestion",
                            source_extractions.c.source_id.in_(source_ids),
                            source_events.c.status == "committed",
                        )
                    )
                ).all()
            )
