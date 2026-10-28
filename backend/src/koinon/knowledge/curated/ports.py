# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from abc import ABC, abstractmethod
from dataclasses import dataclass

from pydantic import Field

from koinon.knowledge.curated.dtos import (
    Frozen,
    Identifier,
    KnowledgeCommitReceipt,
    KnowledgeContent,
    KnowledgeIntent,
)


class NativeCatalogProjection(Frozen):
    """Metadata from exact committed native versions, never a current-content guess."""

    native_workspace_id: Identifier
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = Field(default=None, max_length=4000)
    serving_version_id: Identifier | None = None
    serving_operation_id: Identifier | None = None
    source_asset_ids: tuple[Identifier, ...] = Field(default=(), max_length=500)


class NativeCommitUncertain(Exception):
    """A native commit outcome must be read by its immutable operation ID."""


@dataclass(frozen=True)
class NativeKnowledgeOperation:
    preview: KnowledgeIntent
    originating_token_ids: tuple[str, ...]


class NativeKnowledgeCommitPort(ABC):
    @abstractmethod
    async def projection(
        self, subject: str, tenant_id: str, receipt: KnowledgeCommitReceipt
    ) -> NativeCatalogProjection: ...

    @abstractmethod
    async def head(self, subject: str, tenant_id: str, item_id: str) -> tuple[int, KnowledgeContent]: ...

    @abstractmethod
    async def commit(self, operation: NativeKnowledgeOperation) -> KnowledgeCommitReceipt: ...

    @abstractmethod
    async def receipt(
        self, subject: str, tenant_id: str, operation_id: str, authorization_digest: str
    ) -> KnowledgeCommitReceipt | None: ...


class CuratedCorpusPort(ABC):
    @abstractmethod
    async def admit(self, subject, tenant_id, item_ids) -> tuple: ...

    @abstractmethod
    async def search(
        self, subject, tenant_id, native_workspace_id, admitted, *, query, limit, _capture=None
    ) -> list: ...
