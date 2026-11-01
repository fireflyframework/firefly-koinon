# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Managed native history port; data selection belongs to its repository."""

from typing import Unpack

from flycanon.core.services.sources.lineage.dtos import VerifiedOriginal
from pyfly.container import service

from koinon.knowledge.document_history.ports import (
    DocumentReadScope,
    ExtractionRecord,
    HistoryPage,
    PartContentRecord,
    PartRecord,
    VersionRecord,
)
from koinon.knowledge.document_history.repositories import DocumentHistoryRepository


@service
class NativeDocumentHistory:
    def __init__(self, repository: DocumentHistoryRepository):
        self.repository = repository

    async def versions(
        self, *, page: int = 1, page_size: int = 25, **scope: Unpack[DocumentReadScope]
    ) -> HistoryPage[VersionRecord]:
        return await self.repository.versions(page=page, page_size=page_size, **scope)

    async def version(self, *, source_version_id: str, **scope: Unpack[DocumentReadScope]) -> VersionRecord:
        return await self.repository.version(source_version_id=source_version_id, **scope)

    async def extractions(
        self,
        *,
        source_version_id: str,
        page: int = 1,
        page_size: int = 25,
        **scope: Unpack[DocumentReadScope],
    ) -> HistoryPage[ExtractionRecord]:
        return await self.repository.extractions(
            source_version_id=source_version_id, page=page, page_size=page_size, **scope
        )

    async def parts(
        self,
        *,
        source_version_id: str,
        extraction_id: str,
        kind: str | None = None,
        page: int = 1,
        page_size: int = 25,
        **scope: Unpack[DocumentReadScope],
    ) -> HistoryPage[PartRecord]:
        return await self.repository.parts(
            source_version_id=source_version_id,
            extraction_id=extraction_id,
            kind=kind,
            page=page,
            page_size=page_size,
            **scope,
        )

    async def part(
        self,
        *,
        source_version_id: str,
        extraction_id: str,
        source_part_id: str,
        **scope: Unpack[DocumentReadScope],
    ) -> PartContentRecord:
        return await self.repository.part(
            source_version_id=source_version_id,
            extraction_id=extraction_id,
            source_part_id=source_part_id,
            **scope,
        )

    async def original(
        self, *, source_version_id: str, max_bytes: int, **scope: Unpack[DocumentReadScope]
    ) -> VerifiedOriginal:
        return await self.repository.original(
            source_version_id=source_version_id, max_bytes=max_bytes, **scope
        )

    async def original_identity(self, *, source_version_id=None, **scope):
        return await self.repository.original_identity(source_version_id=source_version_id, **scope)

    async def original_file(self, *, path, max_bytes, source_version_id=None, **scope):
        return await self.repository.original_file(
            path=path, max_bytes=max_bytes, source_version_id=source_version_id, **scope
        )
