# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Event
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException, PayloadTooLargeException

from koinon.assistants.memory.egress_dtos import stored_snapshot
from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import ConversationSnapshot, SourceReference, StoredResult
from koinon.evidence.reviews import EvidenceReviews
from koinon.exports.data import convert_parquet
from koinon.exports.dtos import (
    ConversationExportInput,
    Export,
    ExportCreate,
    ExportPage,
    ExportReview,
    QueryResultExportInput,
)
from koinon.exports.entities import ExportRecord
from koinon.exports.renderers import RenderedExport, render_transcript, safe_filename
from koinon.exports.repositories import KnowledgeExportRepository


@service(name="exports.service")
class KnowledgeExports:
    def __init__(self, exports: KnowledgeExportRepository, reviews: EvidenceReviews):
        self.exports, self.reviews = exports, reviews
        self._downloads = 0

    def _dto(self, row, review):
        result = (
            StoredResult.model_validate(review.snapshot_json)
            if review.request_json["kind"] == "query_result"
            else None
        )
        return Export(
            id=row.id,
            kind=review.request_json["kind"],
            format=review.request_json["format"],
            title=review.title,
            status="cancelled"
            if row.cancelled_at
            else "expired"
            if row.expires_at <= datetime.now(UTC)
            else "ready",
            revision=review.revision,
            completeness=result.completeness if result else "selected_messages",
            row_count=result.row_count if result else None,
            truncated=result.truncated if result else None,
            created_at=row.created_at,
            expires_at=row.expires_at,
        )

    @transactional
    async def preview(
        self, subject, tenant_id, body: ConversationExportInput | QueryResultExportInput
    ) -> ExportReview:
        if isinstance(body, QueryResultExportInput):
            return await self._result_preview(subject, tenant_id, body)
        row = await self.reviews.conversation(subject, tenant_id, body, purpose="export")
        snapshot = stored_snapshot(row.snapshot_json)
        omissions = []
        if not body.include_evidence:
            omissions.append("Source evidence was excluded from this export.")
        elif not snapshot.source_manifest_complete:
            omissions.append("The source manifest is incomplete; this is not a complete evidence archive.")
        if any(message.private_derived for message in snapshot.messages):
            omissions.append("Private attachment files and their metadata are excluded.")
        messages = (
            snapshot.messages
            if body.include_evidence
            else tuple(message.model_copy(update={"source_ids": ()}) for message in snapshot.messages)
        )
        return ExportReview(
            id=row.id,
            revision=row.revision,
            kind="conversation",
            format=body.format,
            title=row.title,
            message_count=len(messages),
            source_count=len(snapshot.sources) if body.include_evidence else 0,
            messages=messages,
            sources=snapshot.sources if body.include_evidence else (),
            source_manifest_complete=snapshot.source_manifest_complete if body.include_evidence else False,
            completeness="selected_messages",
            omissions=tuple(omissions),
            expires_at=row.expires_at,
            identity=snapshot.identity,
        )

    async def _result_preview(self, subject, tenant_id, body):
        row = await self.reviews.query_result(subject, tenant_id, body)
        result = StoredResult.model_validate(row.snapshot_json)
        omissions = ["This export contains the stored execution artifact; it does not rerun the query."]
        if result.completeness == "unknown":
            omissions.append(
                "Historical row cap and truncation are unknown; completeness cannot be verified."
            )
        if not result.snapshot_manifest_complete:
            omissions.append("Historical table snapshot provenance is incomplete.")
        if body.format == "csv" and body.csv_mode == "spreadsheet_safe":
            omissions.append(
                "Spreadsheet-safe CSV prefixes potentially executable text cells with an apostrophe."
            )
        return ExportReview(
            id=row.id,
            revision=row.revision,
            kind="query_result",
            format=body.format,
            title=row.title,
            message_count=0,
            source_count=len(row.manifest_json),
            sources=tuple(SourceReference.model_validate(item) for item in row.manifest_json),
            row_count=result.row_count,
            row_cap=result.row_cap,
            truncated=result.truncated,
            result=result,
            completeness=result.completeness,
            omissions=tuple(omissions),
            expires_at=row.expires_at,
        )

    @transactional
    async def create(self, subject, tenant_id, body: ExportCreate) -> Export:
        self.reviews.settings.validate()
        await self.reviews.catalog._lock_tenant(tenant_id)
        if await self.exports.active_count(subject, tenant_id) >= self.reviews.settings.max_active_exports:
            raise ConflictException(
                "Cancel an existing export before creating another", code="EXPORT_LIMIT_REACHED"
            )
        review = await self.reviews.claim(
            subject, tenant_id, body.review_id, body.expected_revision, purpose="export"
        )
        now = datetime.now(UTC)
        expires = now + timedelta(seconds=self.reviews.settings.export_ttl_seconds)
        if review.request_json["kind"] == "query_result":
            expires = min(expires, StoredResult.model_validate(review.snapshot_json).expires_at)
        tokens = set()
        if review.request_json["kind"] == "conversation":
            tokens.update(stored_snapshot(review.snapshot_json).originating_token_ids)
        if review.creator_token_id:
            tokens.add(review.creator_token_id)
        for token_id in tokens:
            token = await self.reviews.access._token(token_id, subject, tenant_id)
            expires = min(expires, token.expires_at)
        row = ExportRecord(
            id=str(uuid4()),
            review_id=review.id,
            tenant_id=tenant_id,
            owner_subject=subject,
            created_at=now,
            expires_at=expires,
            cancelled_at=None,
        )
        await self.exports.save(row)
        await self.reviews.catalog._audit(subject, tenant_id, "export.created", row.id)
        return self._dto(row, review)

    async def _saved(self, subject, tenant_id, row):
        review = await self.reviews.reviews.find_by_id(row.review_id)
        if review is None or review.tenant_id != tenant_id or review.owner_subject != subject:
            raise AccessDenied("This export is unavailable", code="EXPORT_UNAVAILABLE")
        result = review.request_json["kind"] == "query_result"
        snapshot = (
            StoredResult.model_validate(review.snapshot_json)
            if result
            else stored_snapshot(review.snapshot_json)
        )
        sources = tuple(SourceReference.model_validate(item) for item in review.manifest_json)
        await self.reviews.access.check(
            subject,
            tenant_id,
            sources,
            permission="exports:read",
            originating_token_ids=snapshot.originating_token_ids
            if isinstance(snapshot, ConversationSnapshot)
            else (),
            creator_token_id=review.creator_token_id,
            creator_permission="exports:write",
        )
        if isinstance(snapshot, ConversationSnapshot):
            await self.reviews.memory_check(
                subject,
                tenant_id,
                snapshot,
                permission="exports:read",
                creator_token_id=review.creator_token_id,
                creator_permission="exports:write",
                release=("export", row.id),
            )
        return review, snapshot

    async def _metadata(self, subject, tenant_id, row):
        review = await self.reviews.reviews.find_by_id(row.review_id)
        if review is None or review.tenant_id != tenant_id or review.owner_subject != subject:
            raise AccessDenied("This export is unavailable", code="EXPORT_UNAVAILABLE")
        sources = tuple(SourceReference.model_validate(item) for item in review.manifest_json)
        await self.reviews.access.management(subject, tenant_id, sources, permission="exports:read")
        return review

    async def _row(self, subject, tenant_id, identifier):
        rows = await self.exports.find_all(id=identifier, tenant_id=tenant_id, owner_subject=subject)
        if not rows:
            raise AccessDenied("This export is unavailable", code="EXPORT_UNAVAILABLE")
        return rows[0]

    @transactional(read_only=True, read_from_primary=True)
    async def get(self, subject, tenant_id, identifier) -> Export:
        row = await self._row(subject, tenant_id, identifier)
        review = await self._metadata(subject, tenant_id, row)
        return self._dto(row, review)

    @transactional(read_only=True, read_from_primary=True)
    async def download(self, subject, tenant_id, identifier):
        self.reviews.settings.validate()
        row = await self._row(subject, tenant_id, identifier)
        if row.cancelled_at or row.expires_at <= datetime.now(UTC):
            raise AccessDenied("This export is unavailable", code="EXPORT_UNAVAILABLE")
        review, snapshot = await self._saved(subject, tenant_id, row)
        if self._downloads >= self.reviews.settings.max_concurrent_downloads:
            raise ConflictException(
                "Another download is in progress; try again when it finishes", code="EXPORT_BUSY"
            )
        self._downloads += 1
        try:
            if isinstance(snapshot, StoredResult):
                return await self._data_download(subject, tenant_id, row, review, snapshot)
            rendered = render_transcript(
                snapshot,
                review.request_json["format"],
                include_evidence=review.request_json["include_evidence"],
                exported_at=row.created_at,
            )
            if len(rendered.content) > self.reviews.settings.max_download_bytes:
                raise PayloadTooLargeException(
                    "This export exceeds the download limit", code="EXPORT_TOO_LARGE"
                )
            await self._saved(subject, tenant_id, row)
            return rendered
        finally:
            self._downloads -= 1

    @transactional
    async def cancel(self, subject, tenant_id, identifier):
        row = await self._row(subject, tenant_id, identifier)
        row = await self.exports.find_by_id(row.id, lock=LockMode.PESSIMISTIC_WRITE)
        review = await self.reviews.reviews.find_by_id(row.review_id)
        sources = tuple(SourceReference.model_validate(item) for item in review.manifest_json)
        await self.reviews.access.management(subject, tenant_id, sources, permission="exports:write")
        if row.cancelled_at is None:
            row.cancelled_at = datetime.now(UTC)
            await self.exports.save(row)
            await self.reviews.catalog._audit(subject, tenant_id, "export.cancelled", row.id)

    @transactional(read_only=True, read_from_primary=True)
    async def page(self, subject, tenant_id, **filters) -> ExportPage:
        result = await self.exports.page(subject, tenant_id, **filters)
        items = []
        for row in result["items"]:
            review = await self._metadata(subject, tenant_id, row)
            items.append(self._dto(row, review))
        if not items:
            await self.reviews.catalog.authorize(subject, tenant_id, "exports:read")
        return ExportPage(**{**result, "items": items})

    async def _data_download(self, subject, tenant_id, row, review, result):
        port = self.reviews.results.get()
        if port is None:
            from pyfly.kernel import ServiceUnavailableException

            raise ServiceUnavailableException(
                "Stored result export is not configured", code="STORED_RESULT_UNAVAILABLE"
            )
        maximum = self.reviews.settings.max_download_bytes
        timeout = self.reviews.settings.download_timeout_seconds
        cancelled = Event()
        try:
            async with asyncio.timeout(timeout):
                content = bytearray()
                stream = port.read(subject, tenant_id, result)
                try:
                    async for block in stream:
                        if len(content) + len(block) > maximum:
                            raise PayloadTooLargeException(
                                "Stored result exceeds the download limit", code="EXPORT_TOO_LARGE"
                            )
                        content.extend(block)
                finally:
                    await stream.aclose()
                if len(content) != result.byte_size or sha256(content).hexdigest() != result.revision:
                    raise ConflictException(
                        "Stored result bytes changed; review the result again",
                        code="RESULT_REVISION_CONFLICT",
                    )
                converted = await asyncio.to_thread(
                    convert_parquet,
                    bytes(content),
                    review.request_json["format"],
                    csv_mode=review.request_json["csv_mode"],
                    max_bytes=maximum,
                    timeout_seconds=timeout,
                    cancelled=cancelled.is_set,
                )
                await self._saved(subject, tenant_id, row)
        except ValueError as error:
            raise InvalidRequestException(str(error), code="EXPORT_FORMAT_LIMIT") from error
        except TimeoutError as error:
            raise ConflictException(
                "This export exceeded its execution limit", code="EXPORT_TIMEOUT"
            ) from error
        finally:
            cancelled.set()
        extension = review.request_json["format"]
        return RenderedExport(
            converted,
            {
                "parquet": "application/vnd.apache.parquet",
                "csv": "text/csv; charset=utf-8",
                "jsonl": "application/x-ndjson",
            }[extension],
            safe_filename(review.title + "-stored-result", extension),
            (
                ("X-Koinon-Completeness", result.completeness),
                ("X-Koinon-Stored-Rows", str(result.row_count)),
                ("X-Koinon-Row-Cap", str(result.row_cap) if result.row_cap is not None else "unknown"),
                (
                    "X-Koinon-Truncated",
                    str(result.truncated).lower() if result.truncated is not None else "unknown",
                ),
                ("X-Koinon-Snapshot-Manifest-Complete", str(result.snapshot_manifest_complete).lower()),
            ),
        )
