# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed application queries and native persistence units for document lineage."""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.models.entities.source import SourceRow

type PublicationGuard = Callable[[], AbstractAsyncContextManager[None]]
type StageAuthorization = Callable[[], Awaitable[None]]

type LineageEntity = Literal["head", "version", "artifact", "extraction", "part", "step", "event", "source"]
type LineageRecord = Mapping[str, Any]


@dataclass(frozen=True)
class LineageQuery:
    entity: LineageEntity
    scope: DocumentScope
    source_id: str | None = None
    equal: Mapping[str, str | None] = field(default_factory=dict)
    included: Mapping[str, Sequence[str]] = field(default_factory=dict)
    order: tuple[str, ...] = ()
    limit: int | None = None
    offset: int | None = None
    lock: Literal["update", "share"] | None = None


@dataclass(frozen=True)
class IngestionPartQuery:
    source_id: str | None = None
    extraction_id: str | None = None
    part_ids: tuple[str, ...] | None = None
    projection_chunk_ids: tuple[str, ...] | None = None
    max_rows: int = 1000
    max_bytes: int = 64 * 1024 * 1024


class LineageUnit(Protocol):
    async def first(self, query: LineageQuery) -> LineageRecord | None: ...
    async def one(self, query: LineageQuery) -> LineageRecord: ...
    async def all(self, query: LineageQuery) -> Sequence[LineageRecord]: ...
    async def scalar(self, query: LineageQuery, column: str) -> Any: ...
    async def count(self, query: LineageQuery) -> int: ...
    async def source(self, query: LineageQuery) -> SourceRow | None: ...
    async def perform(self, query: LineageQuery) -> None: ...
    async def insert(
        self, entity: LineageEntity, records: LineageRecord | Sequence[LineageRecord]
    ) -> None: ...
    async def update(self, query: LineageQuery, values: LineageRecord) -> None: ...
    def add_source(self, source: SourceRow) -> None: ...


class LineagePersistence(Protocol):
    def read(self) -> AbstractAsyncContextManager[LineageUnit]: ...
    def write(self) -> AbstractAsyncContextManager[LineageUnit]: ...
    def raw_write(self) -> AbstractAsyncContextManager[Any]: ...
    async def require_schema(self) -> None: ...

    async def ingestion_chunks(
        self, scope: DocumentScope, query: IngestionPartQuery
    ) -> Sequence[LineageRecord]: ...
    async def committed_sources(self, scope: DocumentScope, source_ids: Sequence[str]) -> set[str]: ...
    async def legacy_chunks(
        self, scope: DocumentScope, *predicates: Any, max_rows: int = 1000, max_bytes: int = 64 * 1024 * 1024
    ) -> Sequence[LineageRecord]: ...
