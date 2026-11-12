# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

from pyfly.container import Provider, service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, GoneException, ServiceUnavailableException

from koinon.assistants.memory.egress_dtos import stored_snapshot
from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.evidence.reviews import EvidenceReviews, digest
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_cursors import SourceBrowseCursors
from koinon.security.authority import primary_authority
from koinon.sharing.dtos import (
    Share,
    ShareBrowseInput,
    ShareBrowsePage,
    ShareCreate,
    SharedConversation,
    SharePage,
    ShareReview,
    ShareReviewInput,
)
from koinon.sharing.entities import ConversationShare
from koinon.sharing.repositories import ConversationShareRepository


@service(name="sharing.service")
class ConversationShares:
    def __init__(
        self,
        shares: ConversationShareRepository,
        reviews: EvidenceReviews,
        cursors: Provider[SourceBrowseCursors | None] | None = None,
    ):
        self.shares, self.reviews = shares, reviews
        self.cursors = cursors

    def _dto(self, row, review):
        status = (
            "revoked" if row.revoked_at else "expired" if row.expires_at <= datetime.now(UTC) else "active"
        )
        return Share(
            id=row.id,
            title=review.title,
            revision=review.revision,
            status=status,
            created_at=row.created_at,
            expires_at=row.expires_at,
            revoked_at=row.revoked_at,
        )

    @staticmethod
    def _review_fingerprint(review):
        return digest(
            {
                "revision": review.revision,
                "request": review.request_json,
                "snapshot": review.snapshot_json,
                "sources": review.manifest_json,
                "creator_token_id": review.creator_token_id,
                "title": review.title,
                "owner": review.owner_subject,
                "tenant": review.tenant_id,
                "kind": review.kind,
            }
        )

    @transactional(read_only=True, read_from_primary=True)
    async def _row(self, tenant_id, identifier, *, owner=None):
        rows = await self.shares.find_all(id=identifier, tenant_id=tenant_id)
        if not rows or owner is not None and rows[0].owner_subject != owner:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        return rows[0]

    @transactional(read_only=True, read_from_primary=True)
    async def _review(self, tenant_id, row):
        review = await self.reviews.reviews.find_by_id(row.review_id)
        if (
            review is None
            or review.tenant_id != tenant_id
            or review.owner_subject != row.owner_subject
            or review.kind != "share"
        ):
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        return review

    @transactional(read_only=True, read_from_primary=True)
    async def _confirm(self, tenant_id, identifier, fingerprint, *, active=True):
        row = await self._row(tenant_id, identifier)
        review = await self._review(tenant_id, row)
        if self._review_fingerprint(review) != fingerprint:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        if active and row.revoked_at:
            raise GoneException("This share was revoked by its owner", code="SHARE_REVOKED")
        if active and row.expires_at <= datetime.now(UTC):
            raise GoneException("This share has expired", code="SHARE_EXPIRED")
        return row, review

    async def _saved(
        self, subject, tenant_id, row, *, operation=None, expected_review=None, permission="shares:read"
    ):
        row = await self._row(tenant_id, row.id)
        operation = await self.reviews.preflight_review(
            subject, tenant_id, row.review_id, owner=row.owner_subject, operation=operation
        )
        review = await self._review(tenant_id, row)
        if expected_review is not None and self._review_fingerprint(review) != expected_review:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        operation = await self.reviews.source_operation(subject, tenant_id, review, operation=operation)
        snapshot = stored_snapshot(review.snapshot_json)
        await self.reviews.access.check(
            subject,
            tenant_id,
            snapshot.sources,
            permission=permission,
            owner_subject=row.owner_subject,
            originating_token_ids=snapshot.originating_token_ids,
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write",
        )
        await self.reviews.output_check(subject, tenant_id, snapshot)
        await self.reviews.memory_check(
            row.owner_subject,
            tenant_id,
            snapshot,
            transfer=True,
            consent=snapshot.memory_transfer_consented,
            reader_subject=subject,
            permission=permission,
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write",
            release=("share", row.id),
        )
        if row.revoked_at:
            raise GoneException("This share was revoked by its owner", code="SHARE_REVOKED")
        if row.expires_at <= datetime.now(UTC):
            raise GoneException("This share has expired", code="SHARE_EXPIRED")
        if operation is not None:
            await operation.release()
        row, review = await self._confirm(tenant_id, row.id, self._review_fingerprint(review))
        return row, review, snapshot, operation

    async def preview(self, subject, tenant_id, body: ShareReviewInput) -> ShareReview:
        row = await self.reviews.conversation(subject, tenant_id, body, purpose="share")
        snapshot = stored_snapshot(row.snapshot_json)
        remembered = await self.reviews.memory_check(subject, tenant_id, snapshot)
        operation = await self.reviews.source_operation(subject, tenant_id, row)
        if operation is not None:
            await operation.release()
        return ShareReview(
            id=row.id,
            revision=row.revision,
            title=row.title,
            message_count=len(row.snapshot_json["messages"]),
            source_count=len(row.manifest_json),
            messages=snapshot.messages,
            sources=snapshot.sources,
            source_manifest_complete=snapshot.source_manifest_complete,
            remembered_context_present=remembered,
            identity=snapshot.identity,
            expires_at=row.expires_at,
        )

    async def create(self, subject, tenant_id, body: ShareCreate) -> Share:
        self.reviews.settings.validate()
        prepared = await self.reviews.prepare_claim(
            subject, tenant_id, body.review_id, body.expected_revision, purpose="share"
        )
        snapshot = stored_snapshot(prepared.row.snapshot_json)
        await self.reviews.output_check(subject, tenant_id, snapshot)
        await self.reviews.memory_check(
            subject,
            tenant_id,
            snapshot,
            transfer=True,
            consent=body.include_remembered_context,
            permission="shares:write",
            creator_token_id=prepared.row.creator_token_id,
            creator_permission="shares:write",
        )
        operation = prepared.operation
        if operation is not None:
            await operation.release()
        async with operation.local_fence() if operation is not None else primary_authority(read_only=False):
            row, review = await self._create_local(subject, tenant_id, body, prepared)
        row, review, _, _ = await self._saved(
            subject,
            tenant_id,
            row,
            operation=operation,
            expected_review=self._review_fingerprint(review),
            permission="shares:write",
        )
        return self._dto(row, review)

    async def _create_local(self, subject, tenant_id, body, prepared):
        await self.reviews.catalog._lock_tenant(tenant_id)
        if await self.shares.active_count(subject, tenant_id) >= self.reviews.settings.max_active_shares:
            raise ConflictException(
                "Revoke an existing share before creating another", code="SHARE_LIMIT_REACHED"
            )
        review = await self.reviews.claim_local(subject, tenant_id, prepared, purpose="share")
        now = datetime.now(UTC)
        expires = now + timedelta(hours=body.expires_in_hours)
        snapshot = stored_snapshot(review.snapshot_json)
        snapshot = snapshot.model_copy(update={"memory_transfer_consented": body.include_remembered_context})
        review.snapshot_json = snapshot.model_dump(mode="json")
        await self.reviews.reviews.save(review)
        token_ids = set(snapshot.originating_token_ids)
        if review.creator_token_id:
            token_ids.add(review.creator_token_id)
        for identifier in token_ids:
            token = await self.reviews.access._token(identifier, subject, tenant_id)
            expires = min(expires, token.expires_at)
        row = ConversationShare(
            id=str(uuid4()),
            review_id=review.id,
            tenant_id=tenant_id,
            owner_subject=subject,
            created_at=now,
            expires_at=expires,
            revoked_at=None,
        )
        await self.shares.save(row)
        await self.reviews.catalog._audit(subject, tenant_id, "share.created", row.id)
        return row, review

    async def read(self, subject, tenant_id, identifier) -> SharedConversation:
        row = await self._row(tenant_id, identifier)
        row, review, snapshot, operation = await self._saved(subject, tenant_id, row)
        expected_review = self._review_fingerprint(review)
        resolver = self.reviews.sources.get()
        if resolver is not None:
            snapshot = snapshot.model_copy(
                update={"sources": await resolver.resolve(subject, tenant_id, snapshot.sources)}
            )
        row, review, _, _ = await self._saved(
            subject, tenant_id, row, operation=operation, expected_review=expected_review
        )
        return SharedConversation(
            share=self._dto(row, review),
            messages=snapshot.messages,
            sources=snapshot.sources,
            source_manifest_complete=snapshot.source_manifest_complete,
            identity=snapshot.identity,
        )

    @transactional
    async def revoke(self, subject, tenant_id, identifier):
        rows = await self.shares.find_all(id=identifier, tenant_id=tenant_id, owner_subject=subject)
        if not rows:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        row = await self.shares.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        manifest = await self.shares.management_manifest(subject, tenant_id, row.review_id)
        if manifest is None:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        await self.reviews.access.management(
            subject,
            tenant_id,
            tuple(SourceReference.model_validate(value) for value in manifest[0]),
            permission="shares:write",
        )
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self.shares.save(row)
            await self.reviews.catalog._audit(subject, tenant_id, "share.revoked", row.id)

    async def _metadata(self, subject, tenant_id, row, *, operation=None):
        if row.owner_subject != subject:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        operation = await self.reviews.preflight_review(
            subject, tenant_id, row.review_id, owner=row.owner_subject, operation=operation
        )
        review = await self._review(tenant_id, row)
        sources = tuple(SourceReference.model_validate(item) for item in review.manifest_json)
        await self.reviews.access.management(subject, tenant_id, sources, permission="shares:read")
        operation = await self.reviews.source_operation(subject, tenant_id, review, operation=operation)
        if operation is not None:
            await operation.release()
        _, review = await self._confirm(tenant_id, row.id, self._review_fingerprint(review), active=False)
        return review

    async def page(self, subject, tenant_id, **filters) -> SharePage:
        async with primary_authority(fresh=True):
            result = await self.shares.page(subject, tenant_id, **filters)
        items = []
        for row in result["items"]:
            review = await self._metadata(subject, tenant_id, row)
            items.append(self._dto(row, review))
        if not items:
            await self.reviews.catalog.authorize(subject, tenant_id, "shares:read")
        return SharePage(**{**result, "items": items})

    async def browse(self, subject, tenant_id, body: ShareBrowseInput) -> ShareBrowsePage:
        await self.reviews.catalog.authorize(subject, tenant_id, "shares:read")
        reader = self.reviews.source_reader.get() if self.reviews.source_reader is not None else None
        if reader is None and body.reader_source_connections:
            raise ServiceUnavailableException(
                "Source reader is unavailable", code="SOURCE_READER_UNAVAILABLE"
            )
        operation = await reader.begin(subject, tenant_id, body.reader_source_connections) if reader else None
        cursors = self.cursors.get() if self.cursors is not None else None
        cursors = cursors or SourceBrowseCursors()
        binding = sha256(
            json.dumps(
                {
                    "resource": "shares",
                    "actor": subject,
                    "tenant": tenant_id,
                    "filters": body.model_dump(exclude={"cursor", "reader_source_connections"}),
                    "selection_revision": operation.selection.revision if operation else None,
                    "selections": [
                        choice.model_dump(mode="json") for choice in operation.selection.connections
                    ]
                    if operation
                    else [],
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        position = await cursors.read(subject, tenant_id, binding, body.cursor, resource="shares")
        scan_size = min(body.page_size, 20)
        async with primary_authority(fresh=True):
            identifiers = await self.shares.scan(
                subject,
                tenant_id,
                status=body.status,
                position=position,
                page_size=scan_size,
                local_only=reader is None,
            )
        items = []
        for identifier in identifiers:
            try:
                row = await self._row(tenant_id, identifier, owner=subject)
                review = await self._metadata(subject, tenant_id, row, operation=operation)
            except SourceError as error:
                if error.code == "size_exceeded":
                    raise
                continue
            except AccessDenied:
                continue
            if body.q.strip().casefold() in review.title.casefold():
                items.append(self._dto(row, review))
        if operation is not None:
            await operation.release()
        cursor = (
            await cursors.issue(subject, tenant_id, binding, position + 1, resource="shares")
            if len(identifiers) == scan_size
            else None
        )
        return ShareBrowsePage(items=tuple(items), next_cursor=cursor)
