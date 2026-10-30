# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Scoped immutable ledger reads, separate from mutable source projections."""

from contextlib import contextmanager

from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.core.services.sources.lineage.service import conditions
from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
from flycanon.models.entities.source_lineage import source_artifacts, source_extractions, source_parts
from pyfly.container import repository
from pyfly.kernel import InvalidRequestException, PayloadTooLargeException, ResourceNotFoundException
from sqlalchemy import func, select

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.document_history.mappers import (
    content_record,
    extraction_record,
    page_result,
    part_record,
    version_record,
)
from koinon.knowledge.document_history.pagination import pagination
from koinon.knowledge.document_history.resources import DocumentHistoryResources


@repository(name="knowledge.document_history.repository")
class DocumentHistoryRepository:
    def __init__(self, resources: DocumentHistoryResources):
        self.resources = resources

    def _lineage(self):
        return self.resources.lineage()

    @contextmanager
    def _scope(self, tenant_id, workspace_id, source_id, actor):
        with native_scope("canon", tenant_id, workspace_id, actor):
            yield self._lineage(), DocumentScope(tenant_id, workspace_id, actor), source_id

    async def versions(self, *, page=1, page_size=25, **scope):
        pagination(page, page_size)
        with self._scope(**scope) as (lineage, native, source):
            await lineage.require_schema()
            result = await lineage.history(native, source, page=page, page_size=page_size)
            rows = [version_record(await lineage.version(native, source, row["id"])) for row in result.items]
            return {**page_result(result, lambda row: row), "items": tuple(rows)}

    async def version(self, *, source_version_id, **scope):
        with self._scope(**scope) as (lineage, native, source):
            await lineage.require_schema()
            return version_record(await lineage.version(native, source, source_version_id))

    @staticmethod
    async def _extraction(lineage, scope, source, version, extraction):
        await lineage.version(scope, source, version)
        async with lineage.sources.session() as session:
            row = (
                (
                    await session.execute(
                        select(source_extractions).where(
                            *conditions(source_extractions, scope, source),
                            source_extractions.c.id == extraction,
                            source_extractions.c.version_id == version,
                        )
                    )
                )
                .mappings()
                .first()
            )
        if row is None:
            raise ResourceNotFoundException(
                "Document extraction is unavailable", code="DOCUMENT_EXTRACTION_NOT_FOUND"
            )
        return row

    @staticmethod
    async def _extraction_summary(lineage, scope, source, row):
        async with lineage.sources.session() as session:
            artifact = (
                (
                    await session.execute(
                        select(source_artifacts).where(
                            *conditions(source_artifacts, scope, source),
                            source_artifacts.c.id == row["normalized_artifact_id"],
                        )
                    )
                )
                .mappings()
                .one()
            )
        return extraction_record(row, artifact)

    async def extractions(self, *, source_version_id, page=1, page_size=25, **scope):
        pagination(page, page_size)
        with self._scope(**scope) as (lineage, native, source):
            await lineage.require_schema()
            await lineage.version(native, source, source_version_id)
            result = await lineage.extractions(
                native, source, source_version_id, page=page, page_size=page_size
            )
            rows = [await self._extraction_summary(lineage, native, source, row) for row in result.items]
            values = page_result(result, lambda row: row)
            return {**values, "items": tuple(rows)}

    async def parts(self, *, source_version_id, extraction_id, kind=None, page=1, page_size=25, **scope):
        pagination(page, page_size)
        with self._scope(**scope) as (lineage, native, source):
            await lineage.require_schema()
            await self._extraction(lineage, native, source, source_version_id, extraction_id)
            if kind not in (None, "artifact", "section", "chunk", "page"):
                raise InvalidRequestException("Select a recorded part kind", code="INVALID_PART_KIND")
            filters = [
                *conditions(source_parts, native, source),
                source_parts.c.extraction_id == extraction_id,
            ]
            if kind is not None:
                filters.append(source_parts.c.kind == kind)
            columns = tuple(
                source_parts.c[name]
                for name in (
                    "id",
                    "extraction_id",
                    "kind",
                    "ordinal",
                    "sha256",
                    "page",
                    "char_start",
                    "char_end",
                    "offset_basis",
                    "created_at",
                )
            )
            async with lineage.sources.session() as session:
                total = (
                    await session.execute(
                        select(func.count()).select_from(source_parts).where(*filters),
                    )
                ).scalar_one()
                rows = (
                    (
                        await session.execute(
                            select(*columns)
                            .where(*filters)
                            .order_by(source_parts.c.ordinal, source_parts.c.id)
                            .limit(page_size)
                            .offset((page - 1) * page_size),
                        )
                    )
                    .mappings()
                    .all()
                )
            return dict(
                items=tuple(part_record(row, source_version_id) for row in rows),
                total=total,
                page=page,
                page_size=page_size,
                pages=(total + page_size - 1) // page_size,
                has_next=page * page_size < total,
                has_previous=page > 1,
            )

    async def part(self, *, source_version_id, extraction_id, source_part_id, **scope):
        with self._scope(**scope) as (lineage, native, source):
            await lineage.require_schema()
            await self._extraction(lineage, native, source, source_version_id, extraction_id)
            async with lineage.sources.session() as session:
                kind = await session.scalar(
                    select(source_parts.c.kind).where(
                        *conditions(source_parts, native, source),
                        source_parts.c.extraction_id == extraction_id,
                        source_parts.c.id == source_part_id,
                    )
                )
            parts = await WholeDocumentReader(lineage).resolve_parts(
                native,
                source_id=source,
                source_version_id=source_version_id,
                extraction_id=extraction_id,
                part_ids=(source_part_id,),
            )
            row = parts[0]
            if len(row.text) > 1_000_000 or len(row.text.encode("utf-8")) > 1_048_576:
                raise PayloadTooLargeException(
                    "The exact part exceeds the content read limit", code="DOCUMENT_PART_TOO_LARGE"
                )
            return content_record(row, kind)

    async def original(self, *, source_version_id, max_bytes, **scope):
        with self._scope(**scope) as (lineage, native, source):
            await lineage.require_schema()
            return await lineage.original(native, source, source_version_id, max_bytes=max_bytes)
