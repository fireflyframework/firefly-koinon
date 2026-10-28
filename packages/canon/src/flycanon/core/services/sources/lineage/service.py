# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable raw admission and exact, scoped immutable document reads."""

from contextlib import asynccontextmanager
from hashlib import sha256
from math import ceil
from uuid import uuid4

from pyfly.data.transaction import Propagation, TransactionTemplate
from pyfly.kernel import (
    ConflictException,
    DataIntegrityException,
    InvalidRequestException,
    ResourceNotFoundException,
    ServiceUnavailableException,
)
from sqlalchemy import func, insert, select

from flycanon.core.services.sources.lineage.dtos import (
    Admission,
    DocumentScope,
    LineagePage,
    VerifiedOriginal,
)
from flycanon.models.entities.source import SourceRow
from flycanon.models.entities.source_lineage import (
    source_artifacts,
    source_events,
    source_extractions,
    source_heads,
    source_parts,
    source_versions,
)


def conditions(table, scope, source_id=None):
    result = [table.c.tenant_id == scope.tenant_id, table.c.workspace_id == scope.workspace_id]
    if source_id is not None:
        result.append(table.c.source_id == source_id)
    return result


def identity(scope, source_id):
    return {"tenant_id": scope.tenant_id, "workspace_id": scope.workspace_id, "source_id": source_id}


class DocumentLineage:
    def __init__(self, sources, object_store):
        self.sources = sources
        self.store = object_store

    @asynccontextmanager
    async def unit(self):
        async with TransactionTemplate(
            self.sources.session_factory, propagation=Propagation.REQUIRES_NEW
        ).transaction() as unit:
            if unit is None:
                raise ServiceUnavailableException(
                    "Document storage requires a native transaction", code="DOCUMENT_LINEAGE_UNAVAILABLE"
                )
            yield unit.resource

    async def head(self, scope, source_id):
        async with self.sources.session() as session:
            return (
                (
                    await session.execute(
                        select(source_heads).where(*conditions(source_heads, scope, source_id))
                    )
                )
                .mappings()
                .first()
            )

    async def admit(self, scope: DocumentScope, **kwargs) -> Admission:
        for attempt in range(2):
            try:
                return await self._admit(scope, **kwargs)
            except DataIntegrityException as error:
                if attempt:
                    raise ConflictException(
                        "Concurrent document admission requires reconciliation",
                        code="DOCUMENT_OPERATION_CONFLICT",
                    ) from error
        raise AssertionError("Unreachable admission retry state")

    async def require_schema(self):
        try:
            async with self.sources.session() as session:
                await session.execute(select(source_heads).limit(0))
        except Exception as error:
            raise ServiceUnavailableException(
                "Document version storage is unavailable; check the product document migration",
                code="DOCUMENT_LINEAGE_UNAVAILABLE",
            ) from error

    async def _admit(
        self,
        scope: DocumentScope,
        *,
        logical_key: str,
        operation_id: str,
        content: bytes,
        filename: str | None,
        media_type: str | None,
        source_id: str | None = None,
        expected_source_version_id: str | None = None,
        expected_extraction_id: str | None = None,
    ) -> Admission:
        if (
            not all((scope.tenant_id, scope.workspace_id, scope.actor, logical_key, operation_id))
            or max(len(logical_key), len(operation_id)) > 128
        ):
            raise InvalidRequestException(
                "A scoped logical source and operation are required", code="DOCUMENT_ADMISSION_REQUIRED"
            )
        digest = sha256(content).hexdigest()
        async with self.unit() as session:
            previous = (
                (
                    await session.execute(
                        select(source_versions).where(
                            *conditions(source_versions, scope),
                            source_versions.c.operation_id == operation_id,
                        )
                    )
                )
                .mappings()
                .first()
            )
            if previous is not None:
                artifact = (
                    (
                        await session.execute(
                            select(source_artifacts).where(
                                *conditions(source_artifacts, scope, previous["source_id"]),
                                source_artifacts.c.id == previous["artifact_id"],
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                if (
                    previous["logical_key"] != logical_key
                    or artifact["sha256"] != digest
                    or artifact["bytes"] != len(content)
                    or previous["filename"] != filename
                    or previous["media_type"] != media_type
                    or (source_id is not None and previous["source_id"] != source_id)
                    or (
                        source_id is not None
                        and (previous["predecessor_id"], previous["expected_extraction_id"])
                        != (expected_source_version_id, expected_extraction_id)
                    )
                ):
                    raise ConflictException(
                        "This operation already admitted different document content",
                        code="DOCUMENT_OPERATION_CONFLICT",
                    )
                current = (
                    (
                        await session.execute(
                            select(source_heads)
                            .where(
                                *conditions(source_heads, scope, previous["source_id"]),
                                source_heads.c.logical_key == logical_key,
                            )
                            .with_for_update()
                        )
                    )
                    .mappings()
                    .first()
                )
                actual = (current["version_id"], current["extraction_id"]) if current else None
                expected = (previous["predecessor_id"], previous["expected_extraction_id"])
                if actual != expected:
                    completed = await session.scalar(
                        select(source_extractions.c.id).where(
                            *conditions(source_extractions, scope, previous["source_id"]),
                            source_extractions.c.version_id == previous["id"],
                            source_extractions.c.purpose == "ingestion",
                        )
                    )
                    if completed is None or actual != (previous["id"], completed):
                        raise ConflictException(
                            "Document version or extraction changed before retry; review its current content",
                            code="DOCUMENT_OPERATION_SUPERSEDED"
                            if completed
                            else "DOCUMENT_VERSION_CONFLICT",
                        )
                await self._verified(artifact, len(content))
                return self._admission(previous, artifact)
            head = (
                (
                    await session.execute(
                        select(source_heads)
                        .where(*conditions(source_heads, scope), source_heads.c.logical_key == logical_key)
                        .with_for_update()
                    )
                )
                .mappings()
                .first()
            )
            if head is not None and source_id is not None and head["source_id"] != source_id:
                raise ConflictException("Logical document binding changed", code="DOCUMENT_BINDING_CONFLICT")
            if head is not None and source_id is None:
                raise ConflictException(
                    "This logical document already has an admission; use its reviewed operation",
                    code="DOCUMENT_OPERATION_CONFLICT",
                )
            if source_id is not None:
                observed = (head["version_id"], head["extraction_id"]) if head else (None, None)
                wanted = (expected_source_version_id, expected_extraction_id)
                if observed != wanted:
                    raise ConflictException(
                        "Document version or extraction changed before raw admission",
                        code="DOCUMENT_VERSION_CONFLICT" if all(wanted) else "DOCUMENT_VERSION_REQUIRED",
                    )
            identifier = head["source_id"] if head is not None else source_id or str(uuid4())
            row = (
                (
                    await session.execute(
                        select(SourceRow).where(
                            SourceRow.id == identifier,
                            SourceRow.tenant_id == scope.tenant_id,
                            SourceRow.workspace_id == scope.workspace_id,
                        )
                    )
                )
                .scalars()
                .first()
            )
            if source_id is not None and row is None:
                raise ResourceNotFoundException("Document is unavailable", code="DOCUMENT_NOT_FOUND")
            if head is None:
                existing = (
                    (
                        await session.execute(
                            select(source_heads).where(*conditions(source_heads, scope, identifier))
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing is not None:
                    raise ConflictException(
                        "Document belongs to another logical source", code="DOCUMENT_BINDING_CONFLICT"
                    )
                await session.execute(
                    insert(source_heads).values(**identity(scope, identifier), logical_key=logical_key)
                )
            artifact_id, version_id = str(uuid4()), str(uuid4())
            key = f"koinon/{scope.tenant_id}/{scope.workspace_id}/document-lineage/{identifier}/{artifact_id}"
            artifact = {
                "id": artifact_id,
                **identity(scope, identifier),
                "role": "raw",
                "sha256": digest,
                "bytes": len(content),
                "media_type": media_type,
                "object_key": key,
            }
            try:
                await self.store.put(key, content, media_type)
                await self._verified(artifact, len(content))
            except Exception as error:
                raise ServiceUnavailableException(
                    "Durable original storage is required before processing",
                    code="DOCUMENT_ORIGINAL_UNAVAILABLE",
                ) from error
            if row is None:
                session.add(
                    SourceRow(
                        id=identifier,
                        tenant_id=scope.tenant_id,
                        workspace_id=scope.workspace_id,
                        kind="unknown",
                        status="pending",
                        filename=filename,
                        content_type=media_type,
                        content_sha256="",
                        content_bytes=0,
                        metadata_json={},
                    )
                )
            version = {
                "id": version_id,
                **identity(scope, identifier),
                "artifact_id": artifact_id,
                "logical_key": logical_key,
                "operation_id": operation_id,
                "filename": filename,
                "media_type": media_type,
                "actor": scope.actor,
                "predecessor_id": head["version_id"] if head else None,
                "expected_extraction_id": head["extraction_id"] if head else None,
            }
            await session.execute(insert(source_artifacts).values(**artifact))
            await session.execute(insert(source_versions).values(**version))
            await session.execute(
                insert(source_events).values(
                    id=str(uuid4()), **identity(scope, identifier), version_id=version_id, status="admitted"
                )
            )
            return self._admission(version, artifact)

    @staticmethod
    def _admission(version, artifact):
        return Admission(
            version["source_id"],
            version["id"],
            artifact["id"],
            artifact["sha256"],
            artifact["bytes"],
            artifact["object_key"],
            version["predecessor_id"],
            version["expected_extraction_id"],
        )

    async def _verified(self, artifact, max_bytes):
        try:
            data = await self.store.get_bounded(artifact["object_key"], max_bytes)
        except FileNotFoundError as error:
            raise ResourceNotFoundException(
                "Document version bytes are unavailable", code="DOCUMENT_ORIGINAL_UNAVAILABLE"
            ) from error
        if len(data) != artifact["bytes"] or sha256(data).hexdigest() != artifact["sha256"]:
            raise ServiceUnavailableException(
                "Document original failed integrity verification", code="DOCUMENT_ORIGINAL_UNAVAILABLE"
            )
        return data

    async def original(self, scope, source_id, version_id, *, max_bytes):
        async with self.sources.session() as session:
            version = (
                (
                    await session.execute(
                        select(source_versions).where(
                            *conditions(source_versions, scope, source_id), source_versions.c.id == version_id
                        )
                    )
                )
                .mappings()
                .first()
            )
            if version is None:
                raise ResourceNotFoundException(
                    "Document version is unavailable", code="DOCUMENT_VERSION_NOT_FOUND"
                )
            artifact = (
                (
                    await session.execute(
                        select(source_artifacts).where(
                            *conditions(source_artifacts, scope, source_id),
                            source_artifacts.c.id == version["artifact_id"],
                        )
                    )
                )
                .mappings()
                .one()
            )
        data = await self._verified(artifact, max_bytes)
        return VerifiedOriginal(
            version_id,
            artifact["sha256"],
            artifact["bytes"],
            version["filename"],
            version["media_type"],
            data,
        )

    async def history(self, scope, source_id, *, page=1, page_size=25):
        return await self._page(source_versions, scope, source_id, page=page, page_size=page_size)

    async def committed(self, scope, source_id, version_id):
        async with self.sources.session() as session:
            return (
                (
                    await session.execute(
                        select(source_extractions).where(
                            *conditions(source_extractions, scope, source_id),
                            source_extractions.c.version_id == version_id,
                            source_extractions.c.purpose == "ingestion",
                        )
                    )
                )
                .mappings()
                .first()
            )

    async def failed(self, scope, admission, reason):
        async with self.unit() as session:
            await session.execute(
                insert(source_events).values(
                    id=str(uuid4()),
                    **identity(scope, admission.source_id),
                    version_id=admission.version_id,
                    status="failed",
                    reason_code=reason[:64],
                )
            )

    async def parts(self, scope, source_id, extraction_id, *, kind=None, page=1, page_size=50):
        if kind not in (None, "artifact", "section", "chunk", "page"):
            raise InvalidRequestException("Select a recorded part kind", code="INVALID_PART_KIND")
        extra = [source_parts.c.extraction_id == extraction_id]
        if kind is not None:
            extra.append(source_parts.c.kind == kind)
        return await self._page(source_parts, scope, source_id, extra=extra, page=page, page_size=page_size)

    async def extractions(self, scope, source_id, version_id, *, page=1, page_size=25):
        return await self._page(
            source_extractions,
            scope,
            source_id,
            extra=[source_extractions.c.version_id == version_id],
            page=page,
            page_size=page_size,
        )

    async def resolve_parts(self, scope, source_id, extraction_id, part_ids):
        if not 1 <= len(part_ids) <= 100 or len(set(part_ids)) != len(part_ids):
            raise InvalidRequestException("Select from1 to100 distinct parts", code="INVALID_PARTS")
        async with self.sources.session() as session:
            rows = (
                (
                    await session.execute(
                        select(source_parts).where(
                            *conditions(source_parts, scope, source_id),
                            source_parts.c.extraction_id == extraction_id,
                            source_parts.c.id.in_(part_ids),
                        )
                    )
                )
                .mappings()
                .all()
            )
        if len(rows) != len(part_ids):
            raise ResourceNotFoundException(
                "One or more exact document parts are unavailable", code="DOCUMENT_PART_NOT_FOUND"
            )
        found = {row["id"]: dict(row) for row in rows}
        return tuple(found[identifier] for identifier in part_ids)

    async def version(self, scope, source_id, version_id):
        async with self.sources.session() as session:
            row = (
                (
                    await session.execute(
                        select(source_versions).where(
                            *conditions(source_versions, scope, source_id), source_versions.c.id == version_id
                        )
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise ResourceNotFoundException(
                    "Document version is unavailable", code="DOCUMENT_VERSION_NOT_FOUND"
                )
            artifact = (
                (
                    await session.execute(
                        select(source_artifacts).where(
                            *conditions(source_artifacts, scope, source_id),
                            source_artifacts.c.id == row["artifact_id"],
                        )
                    )
                )
                .mappings()
                .one()
            )
        return {**dict(row), "sha256": artifact["sha256"], "bytes": artifact["bytes"], "status": "recorded"}

    async def _page(self, table, scope, source_id, *, extra=(), page=1, page_size=25):
        if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise InvalidRequestException(
                "Use a positive page and page size from1 to100", code="INVALID_PAGE"
            )
        async with self.sources.session() as session:
            where = [*conditions(table, scope, source_id), *extra]
            total = (
                await session.execute(select(func.count()).select_from(table).where(*where))
            ).scalar_one()
            ordering = (
                (table.c.ordinal, table.c.id)
                if "ordinal" in table.c
                else (table.c.created_at.desc(), table.c.id)
            )
            rows = (
                (
                    await session.execute(
                        select(table)
                        .where(*where)
                        .order_by(*ordering)
                        .limit(page_size)
                        .offset((page - 1) * page_size)
                    )
                )
                .mappings()
                .all()
            )
        return LineagePage(tuple(dict(row) for row in rows), total, page, page_size, ceil(total / page_size))
