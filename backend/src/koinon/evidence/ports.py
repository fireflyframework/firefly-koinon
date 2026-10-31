# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from koinon.evidence.dtos import ConversationSnapshot, SourceReference, StoredResult


@runtime_checkable
class ConversationSnapshotPort(Protocol):
    async def snapshot(
        self, subject: str, tenant_id: str, thread_id: str, message_ids: list[str]
    ) -> ConversationSnapshot: ...


@runtime_checkable
class StoredResultPort(Protocol):
    async def describe(
        self, subject: str, tenant_id: str, dataset_id: str, query_id: str
    ) -> StoredResult: ...

    def read(self, subject: str, tenant_id: str, result: StoredResult) -> AsyncIterator[bytes]: ...


@runtime_checkable
class SourceResolverPort(Protocol):
    async def resolve(
        self, subject: str, tenant_id: str, sources: tuple[SourceReference, ...]
    ) -> tuple[SourceReference, ...]: ...


@runtime_checkable
class WriteSourceResolverPort(Protocol):
    async def resolve_for_write(
        self, subject: str, tenant_id: str, sources: tuple[SourceReference, ...]
    ) -> tuple[SourceReference, ...]: ...


@runtime_checkable
class TransitiveSourceResolverPort(Protocol):
    async def resolve_bounds(
        self, subject: str, tenant_id: str, sources: tuple[SourceReference, ...]
    ) -> tuple[SourceReference, ...]: ...
