# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable raw admission and exact, scoped immutable document reads."""

from collections.abc import Sequence
from contextlib import asynccontextmanager
from hashlib import sha256
from typing import Any
from uuid import uuid4

from pyfly.container import service
from pyfly.kernel import (
    ConflictException,
    DataIntegrityException,
    InvalidRequestException,
    ResourceNotFoundException,
    ServiceUnavailableException,
)

from flycanon.core.mappers.source_lineage_mapper import identity as identity
from flycanon.core.mappers.source_lineage_mapper import to_admission, to_lineage_page
from flycanon.core.services.sources.lineage.dtos import (
    Admission,
    DocumentScope,
    LineagePage,
    VerifiedOriginal,
)
from flycanon.core.services.sources.lineage.ports import LineagePersistence, LineageQuery, LineageRecord
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.models.entities.source import SourceRow
from flycanon.models.repositories.lineage.repository import NativeLineageRepository
from flycanon.models.repositories.lineage.statements import conditions as conditions
from flycanon.models.repositories.source_repository import SourceRepository


@service(name="canon.DocumentLineage")
class DocumentLineage:
    def __init__(
        self,
        sources: SourceRepository,
        object_store: ObjectStore,
        repository: LineagePersistence | None = None,
    ) -> None:
        self.sources = sources
        self.store = object_store
        # Compatibility construction only borrows the supplied repository's native resource.
        self.repository = repository if repository is not None else NativeLineageRepository(sources)

    @asynccontextmanager
    async def unit(self):
        """Compatibility native session seam; application workflows use typed units."""
        async with self.repository.raw_write() as session:
            yield session

    async def head(self, scope: DocumentScope, source_id: str) -> LineageRecord | None:
        async with self.repository.read() as session:
            return await session.first(LineageQuery("head", scope, source_id=source_id))

    async def admit(
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
        for attempt in range(2):
            try:
                return await self._admit(
                    scope,
                    logical_key=logical_key,
                    operation_id=operation_id,
                    content=content,
                    filename=filename,
                    media_type=media_type,
                    source_id=source_id,
                    expected_source_version_id=expected_source_version_id,
                    expected_extraction_id=expected_extraction_id,
                )
            except DataIntegrityException as error:
                if attempt:
                    raise ConflictException(
                        "Concurrent document admission requires reconciliation",
                        code="DOCUMENT_OPERATION_CONFLICT",
                    ) from error
        raise AssertionError("Unreachable admission retry state")

    async def require_schema(self) -> None:
        try:
            await self.repository.require_schema()
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
        async with self.repository.write() as session:
            previous = await session.first(
                LineageQuery("version", scope, equal={"operation_id": operation_id})
            )
            if previous is not None:
                artifact = await session.one(
                    LineageQuery(
                        "artifact",
                        scope,
                        source_id=previous["source_id"],
                        equal={"id": previous["artifact_id"]},
                    )
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
                current = await session.first(
                    LineageQuery(
                        "head",
                        scope,
                        source_id=previous["source_id"],
                        lock="update",
                        equal={"logical_key": logical_key},
                    )
                )
                actual = (current["version_id"], current["extraction_id"]) if current else None
                expected = (previous["predecessor_id"], previous["expected_extraction_id"])
                if actual != expected:
                    completed = await session.scalar(
                        LineageQuery(
                            "extraction",
                            scope,
                            source_id=previous["source_id"],
                            equal={"version_id": previous["id"], "purpose": "ingestion"},
                        ),
                        "id",
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
            head = await session.first(
                LineageQuery("head", scope, lock="update", equal={"logical_key": logical_key})
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
            row = await session.source(
                LineageQuery(
                    "source",
                    scope,
                    equal={
                        "id": identifier,
                        "tenant_id": scope.tenant_id,
                        "workspace_id": scope.workspace_id,
                    },
                )
            )
            if source_id is not None and row is None:
                raise ResourceNotFoundException("Document is unavailable", code="DOCUMENT_NOT_FOUND")
            if head is None:
                existing = await session.first(LineageQuery("head", scope, source_id=identifier))
                if existing is not None:
                    raise ConflictException(
                        "Document belongs to another logical source", code="DOCUMENT_BINDING_CONFLICT"
                    )
                await session.insert("head", dict(**identity(scope, identifier), logical_key=logical_key))
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
                session.add_source(
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
            await session.insert("artifact", dict(**artifact))
            await session.insert("version", dict(**version))
            await session.insert(
                "event",
                dict(
                    id=str(uuid4()), **identity(scope, identifier), version_id=version_id, status="admitted"
                ),
            )
            return self._admission(version, artifact)

    @staticmethod
    def _admission(version, artifact):
        return to_admission(version, artifact)

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

    async def original(
        self, scope: DocumentScope, source_id: str, version_id: str, *, max_bytes: int
    ) -> VerifiedOriginal:
        async with self.repository.read() as session:
            version = await session.first(
                LineageQuery("version", scope, source_id=source_id, equal={"id": version_id})
            )
            if version is None:
                raise ResourceNotFoundException(
                    "Document version is unavailable", code="DOCUMENT_VERSION_NOT_FOUND"
                )
            artifact = await session.one(
                LineageQuery("artifact", scope, source_id=source_id, equal={"id": version["artifact_id"]})
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

    async def history(
        self, scope: DocumentScope, source_id: str, *, page: int = 1, page_size: int = 25
    ) -> LineagePage:
        return await self._page("version", scope, source_id, page=page, page_size=page_size)

    async def committed(self, scope: DocumentScope, source_id: str, version_id: str) -> LineageRecord | None:
        async with self.repository.read() as session:
            return await session.first(
                LineageQuery(
                    "extraction",
                    scope,
                    source_id=source_id,
                    equal={"version_id": version_id, "purpose": "ingestion"},
                )
            )

    async def failed(self, scope: DocumentScope, admission: Admission, reason: str) -> None:
        async with self.repository.write() as session:
            await session.insert(
                "event",
                dict(
                    id=str(uuid4()),
                    **identity(scope, admission.source_id),
                    version_id=admission.version_id,
                    status="failed",
                    reason_code=reason[:64],
                ),
            )

    async def parts(
        self,
        scope: DocumentScope,
        source_id: str,
        extraction_id: str,
        *,
        kind: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> LineagePage:
        if kind not in (None, "artifact", "section", "chunk", "page"):
            raise InvalidRequestException("Select a recorded part kind", code="INVALID_PART_KIND")
        equal = {"extraction_id": extraction_id}
        if kind is not None:
            equal["kind"] = kind
        return await self._page("part", scope, source_id, equal=equal, page=page, page_size=page_size)

    async def extractions(
        self, scope: DocumentScope, source_id: str, version_id: str, *, page: int = 1, page_size: int = 25
    ) -> LineagePage:
        return await self._page(
            "extraction", scope, source_id, equal={"version_id": version_id}, page=page, page_size=page_size
        )

    async def resolve_parts(
        self, scope: DocumentScope, source_id: str, extraction_id: str, part_ids: Sequence[str]
    ) -> tuple[LineageRecord, ...]:
        if not 1 <= len(part_ids) <= 100 or len(set(part_ids)) != len(part_ids):
            raise InvalidRequestException("Select from1 to100 distinct parts", code="INVALID_PARTS")
        async with self.repository.read() as session:
            rows = await session.all(
                LineageQuery(
                    "part",
                    scope,
                    source_id=source_id,
                    equal={"extraction_id": extraction_id},
                    included={"id": part_ids},
                )
            )
        if len(rows) != len(part_ids):
            raise ResourceNotFoundException(
                "One or more exact document parts are unavailable", code="DOCUMENT_PART_NOT_FOUND"
            )
        found = {row["id"]: dict(row) for row in rows}
        return tuple(found[identifier] for identifier in part_ids)

    async def version(self, scope: DocumentScope, source_id: str, version_id: str) -> dict[str, Any]:
        async with self.repository.read() as session:
            row = await session.first(
                LineageQuery("version", scope, source_id=source_id, equal={"id": version_id})
            )
            if row is None:
                raise ResourceNotFoundException(
                    "Document version is unavailable", code="DOCUMENT_VERSION_NOT_FOUND"
                )
            artifact = await session.one(
                LineageQuery("artifact", scope, source_id=source_id, equal={"id": row["artifact_id"]})
            )
        return {**dict(row), "sha256": artifact["sha256"], "bytes": artifact["bytes"], "status": "recorded"}

    async def _page(self, entity, scope, source_id, *, equal=None, page=1, page_size=25):
        if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise InvalidRequestException(
                "Use a positive page and page size from1 to100", code="INVALID_PAGE"
            )
        query = LineageQuery(entity, scope, source_id=source_id, equal=equal or {})
        async with self.repository.read() as session:
            total = await session.count(query)
            rows = await session.all(
                LineageQuery(
                    entity,
                    scope,
                    source_id=source_id,
                    equal=equal or {},
                    order=("ordinal", "id") if entity == "part" else ("-created_at", "id"),
                    limit=page_size,
                    offset=(page - 1) * page_size,
                )
            )
        return to_lineage_page(rows, total, page, page_size)
