# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit bounded cleanup retains consent rows and refuses any admitted intake."""

from datetime import UTC, datetime

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, ServiceUnavailableException

from koinon.catalog.errors import AccessDenied
from koinon.knowledge.curated.authority import CuratedAuthority
from koinon.knowledge.curated.dtos import KnowledgeDestination
from koinon.knowledge.external_reviews.file_dtos import (
    CHUNK_BYTES,
    ExternalFileCleanupInput,
    ExternalFileCleanupResult,
    ExternalFileCleanupReview,
    ExternalFileReviewInput,
)
from koinon.knowledge.external_reviews.file_storage import ExternalReviewFileStorage
from koinon.knowledge.external_reviews.repositories import ExternalFileReviewRepository


@service(name="knowledge.external_reviews.cleanup")
class ExternalFileCleanup:
    def __init__(
        self,
        rows: ExternalFileReviewRepository,
        authority: CuratedAuthority,
        storage: ExternalReviewFileStorage,
    ):
        self.rows, self.authority, self.storage = rows, authority, storage

    async def load(self, subject, tenant_id, identifier):
        row = await self.rows.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("This private file cleanup is unavailable", code="EXTERNAL_REVIEW_UNAVAILABLE")
        expected = KnowledgeDestination.model_validate(row.destination_json)
        await self.authority.catalog.authorize(subject, tenant_id, "settings:write", expected.workspace_id)
        actual = await self.authority.destination(subject, tenant_id, expected.id, write=False)
        if (actual.id, actual.workspace_id, actual.project_id) != (
            expected.id,
            expected.workspace_id,
            expected.project_id,
        ):
            raise AccessDenied("The file destination changed", code="EXTERNAL_REVIEW_UNAVAILABLE")
        if self.authority.catalog.restriction:
            entry = await self.authority.catalog.get(subject, tenant_id, expected.id)
            await self.authority.catalog.restriction.resource(subject, entry, write=True)
        if (
            row.confirmation_key is not None
            or row.source_id is not None
            or row.receipt_json is not None
            or (row.status not in {"uploading", "preview", "cancelled"})
        ):
            raise ConflictException(
                "Retain all admitted or uncertain intake evidence", code="EXTERNAL_CLEANUP_INTAKE_PROTECTED"
            )
        if row.status != "cancelled" and row.expires_at > datetime.now(UTC):
            raise ConflictException(
                "Cancel the file review or wait for expiry", code="EXTERNAL_CLEANUP_NOT_DUE"
            )
        return row

    @transactional
    async def next(self, subject, tenant_id, identifier):
        row = await self.load(subject, tenant_id, identifier)
        request = ExternalFileReviewInput.model_validate(row.request_json)
        chunks = (request.size_bytes + CHUNK_BYTES - 1) // CHUNK_BYTES
        total = chunks + 1
        if (
            not 0 <= row.gc_cursor <= total
            or row.gc_status not in {"none", "purging", "purged"}
            or (row.gc_status == "purged") != (row.gc_cursor == total)
        ):
            raise ConflictException("Inspect the retained cleanup cursor", code="EXTERNAL_CLEANUP_CONFLICT")
        if row.gc_status != "purged":
            row.status, row.nonce_sha256, row.gc_status = "cancelled", None, "purging"
            await self.rows.save(row)
        suffix = f"chunks/{row.gc_cursor}" if row.gc_cursor < chunks else "original"
        return row, suffix, total

    @transactional
    async def advance(self, subject, tenant_id, identifier, cursor, total):
        row = await self.load(subject, tenant_id, identifier)
        if row.gc_status != "purging" or row.gc_cursor != cursor:
            raise ConflictException("Another cleanup advanced this cursor", code="EXTERNAL_CLEANUP_CONFLICT")
        row.gc_cursor += 1
        if row.gc_cursor == total:
            row.gc_status = "purged"
        await self.rows.save(row)

    async def cleanup(self, subject: str, tenant_id: str, values: object) -> ExternalFileCleanupResult:
        request = ExternalFileCleanupInput.model_validate(values)
        remaining, results = request.max_objects, []
        for identifier in request.review_ids:
            row, suffix, total = await self.next(subject, tenant_id, identifier)
            while remaining and row.gc_status != "purged":
                try:
                    await self.storage.purge(row, suffix)
                except OSError:
                    raise ServiceUnavailableException(
                        "Private cleanup did not finish; resume its retained cursor",
                        code="EXTERNAL_CLEANUP_UNAVAILABLE",
                    ) from None
                await self.advance(subject, tenant_id, identifier, row.gc_cursor, total)
                remaining -= 1
                row, suffix, total = await self.next(subject, tenant_id, identifier)
            results.append(
                ExternalFileCleanupReview.model_validate(
                    {
                        "id": row.id,
                        "status": row.gc_status,
                        "processed_objects": row.gc_cursor,
                        "total_objects": total,
                    }
                )
            )
            if remaining == 0:
                break
        return ExternalFileCleanupResult(reviews=tuple(results))
