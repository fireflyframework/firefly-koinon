# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import (
    ConflictException,
    PayloadTooLargeException,
    ResourceNotFoundException,
    ServiceUnavailableException,
)

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.evidence.access import EvidenceAccess
from koinon.evidence.dtos import SourceReference
from koinon.evidence.entities import EvidenceReview
from koinon.evidence.ports import ConversationSnapshotPort, SourceResolverPort, StoredResultPort
from koinon.evidence.repositories import EvidenceReviewRepository
from koinon.evidence.settings import EvidenceSettings
from koinon.exports.dtos import MessageSelection, QueryResultExportInput


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@service(name="evidence.reviews")
class EvidenceReviews:
    def __init__(
        self,
        reviews: EvidenceReviewRepository,
        access: EvidenceAccess,
        catalog: CatalogService,
        settings: EvidenceSettings,
        snapshots: Provider[ConversationSnapshotPort | None],
        sources: Provider[SourceResolverPort | None],
        results: Provider[StoredResultPort | None],
    ):
        self.reviews, self.access, self.catalog, self.settings = reviews, access, catalog, settings
        self.snapshots, self.sources, self.results = snapshots, sources, results

    async def _conversation(self, subject, tenant_id, request, purpose):
        port = self.snapshots.get()
        if port is None:
            raise ServiceUnavailableException(
                "Conversation export is not configured", code="CONVERSATION_SNAPSHOT_UNAVAILABLE"
            )
        snapshot = await port.snapshot(subject, tenant_id, request.thread_id, request.message_ids)
        if (
            snapshot.owner_subject != subject
            or snapshot.tenant_id != tenant_id
            or snapshot.thread_id != request.thread_id
            or set(request.message_ids) != {m.id for m in snapshot.messages}
        ):
            raise AccessDenied("This conversation is unavailable", code="EVIDENCE_UNAVAILABLE")
        if purpose == "share":
            if any(message.private_derived for message in snapshot.messages):
                raise ConflictException(
                    "Answers derived from a private attachment cannot be shared",
                    code="PRIVATE_ATTACHMENT_SHARE_BLOCKED",
                )
            if not snapshot.source_manifest_complete:
                raise ConflictException(
                    "Review a complete source manifest before sharing", code="EVIDENCE_MANIFEST_INCOMPLETE"
                )
        await self.access.check(
            subject,
            tenant_id,
            snapshot.sources,
            permission="shares:write" if purpose == "share" else "exports:write",
            originating_token_ids=snapshot.originating_token_ids,
        )
        resolver = self.sources.get()
        if resolver is not None:
            snapshot = snapshot.model_copy(
                update={"sources": await resolver.resolve(subject, tenant_id, snapshot.sources)}
            )
        payload = snapshot.model_dump(mode="json")
        if len(json.dumps(payload, ensure_ascii=False).encode()) > self.settings.max_snapshot_bytes:
            raise PayloadTooLargeException(
                "Select fewer messages for this export or share", code="SNAPSHOT_TOO_LARGE"
            )
        return snapshot

    async def _result(self, subject, tenant_id, request):
        port = self.results.get()
        if port is None:
            raise ServiceUnavailableException(
                "Stored result export is not configured", code="STORED_RESULT_UNAVAILABLE"
            )
        asset = await self.catalog.get(subject, tenant_id, request.dataset_id)
        if asset.kind != "dataset":
            raise AccessDenied("Select an authorized dataset result", code="EVIDENCE_UNAVAILABLE")
        await self.catalog.authorize(subject, tenant_id, "exports:write", asset.workspace_id)
        result = await port.describe(subject, tenant_id, request.dataset_id, request.query_id)
        if result.asset_id != request.dataset_id or result.query_id != request.query_id:
            raise AccessDenied("This result is unavailable", code="EVIDENCE_UNAVAILABLE")
        if result.byte_size == 0:
            raise ResourceNotFoundException(
                "This empty execution stored no Parquet artifact or schema",
                code="RESULT_ARTIFACT_UNAVAILABLE",
            )
        if result.expires_at <= datetime.now(UTC):
            raise ConflictException(
                "This stored result expired; it will not be rerun automatically", code="RESULT_EXPIRED"
            )
        if result.byte_size > self.settings.max_download_bytes:
            raise PayloadTooLargeException(
                "Stored result exceeds the download limit", code="EXPORT_TOO_LARGE"
            )
        source = SourceReference(
            id=result.query_id, asset_id=asset.id, title=asset.name, kind="dataset", query_id=result.query_id
        )
        await self.access.check(subject, tenant_id, (source,), permission="exports:write")
        return result, (source,)

    @transactional
    async def query_result(self, subject, tenant_id, request: QueryResultExportInput):
        self.settings.validate()
        await self.catalog._lock_tenant(tenant_id)
        if await self.reviews.active_count(subject, tenant_id) >= self.settings.max_active_reviews:
            raise ConflictException(
                "Finish or wait for an existing review before creating another", code="REVIEW_LIMIT_REACHED"
            )
        result, sources = await self._result(subject, tenant_id, request)
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        payload, values = result.model_dump(mode="json"), request.model_dump(mode="json")
        now = datetime.now(UTC)
        row = EvidenceReview(
            id=str(uuid4()),
            tenant_id=tenant_id,
            owner_subject=subject,
            kind="export",
            title=sources[0].title,
            revision=digest({"request": values, "snapshot": payload}),
            request_json=values,
            snapshot_json=payload,
            manifest_json=[source.model_dump(mode="json") for source in sources],
            creator_token_id=grant.id if grant else None,
            created_at=now,
            expires_at=min(result.expires_at, now + timedelta(seconds=self.settings.review_ttl_seconds)),
            consumed_at=None,
        )
        await self.reviews.save(row)
        return row

    @transactional
    async def conversation(self, subject, tenant_id, request: MessageSelection, *, purpose):
        self.settings.validate()
        if purpose not in {"export", "share"}:
            raise ValueError("Unsupported review purpose")
        await self.catalog._lock_tenant(tenant_id)
        if await self.reviews.active_count(subject, tenant_id) >= self.settings.max_active_reviews:
            raise ConflictException(
                "Finish or wait for an existing review before creating another", code="REVIEW_LIMIT_REACHED"
            )
        snapshot = await self._conversation(subject, tenant_id, request, purpose)
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        payload = snapshot.model_dump(mode="json")
        values = request.model_dump(mode="json")
        now = datetime.now(UTC)
        review = EvidenceReview(
            id=str(uuid4()),
            tenant_id=tenant_id,
            owner_subject=subject,
            kind=purpose,
            title=snapshot.title,
            revision=digest({"request": values, "snapshot": payload}),
            request_json=values,
            snapshot_json=payload,
            manifest_json=[source.model_dump(mode="json") for source in snapshot.sources],
            creator_token_id=grant.id if grant else None,
            created_at=now,
            expires_at=now + timedelta(seconds=self.settings.review_ttl_seconds),
            consumed_at=None,
        )
        await self.reviews.save(review)
        return review

    @transactional
    async def claim(self, subject, tenant_id, review_id, expected_revision, *, purpose):
        rows = await self.reviews.find_all(id=review_id, tenant_id=tenant_id, owner_subject=subject)
        if not rows:
            raise AccessDenied("This review is unavailable", code="REVIEW_UNAVAILABLE")
        row = await self.reviews.find_by_id(review_id, lock=LockMode.PESSIMISTIC_WRITE)
        if (
            row.kind != purpose
            or row.revision != expected_revision
            or row.consumed_at is not None
            or row.expires_at <= datetime.now(UTC)
        ):
            raise ConflictException("Review the current content before continuing", code="REVIEW_STALE")
        if row.request_json.get("kind") == "query_result":
            if purpose != "export":
                raise ConflictException("Review this content before continuing", code="REVIEW_STALE")
            request = QueryResultExportInput.model_validate(row.request_json)
            snapshot, _ = await self._result(subject, tenant_id, request)
        else:
            request = MessageSelection(
                thread_id=row.request_json["thread_id"], message_ids=row.request_json["message_ids"]
            )
            snapshot = await self._conversation(subject, tenant_id, request, purpose)
        if (
            digest({"request": row.request_json, "snapshot": snapshot.model_dump(mode="json")})
            != row.revision
        ):
            raise ConflictException(
                "The conversation or its sources changed; review it again", code="REVIEW_STALE"
            )
        grant = await self.catalog.restriction.grant(subject) if self.catalog.restriction else None
        row.creator_token_id = grant.id if grant else None
        row.consumed_at = datetime.now(UTC)
        await self.reviews.save(row)
        return row
