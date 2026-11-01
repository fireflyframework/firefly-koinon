# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, GoneException

from koinon.assistants.memory.egress_dtos import stored_snapshot
from koinon.catalog.errors import AccessDenied
from koinon.evidence.dtos import SourceReference
from koinon.evidence.reviews import EvidenceReviews
from koinon.sharing.dtos import (
    Share,
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
    def __init__(self, shares: ConversationShareRepository, reviews: EvidenceReviews):
        self.shares, self.reviews = shares, reviews

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

    async def _saved(self, subject, tenant_id, row):
        review = await self.reviews.reviews.find_by_id(row.review_id)
        if review is None or review.tenant_id != tenant_id or review.owner_subject != row.owner_subject:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        snapshot = stored_snapshot(review.snapshot_json)
        await self.reviews.access.check(
            subject,
            tenant_id,
            snapshot.sources,
            permission="shares:read",
            owner_subject=row.owner_subject,
            originating_token_ids=snapshot.originating_token_ids,
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write",
        )
        await self.reviews.output_check(row.owner_subject, tenant_id, snapshot)
        await self.reviews.memory_check(
            row.owner_subject,
            tenant_id,
            snapshot,
            transfer=True,
            consent=snapshot.memory_transfer_consented,
            reader_subject=subject,
            permission="shares:read",
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write",
            release=("share", row.id),
        )
        return review, snapshot

    @transactional
    async def preview(self, subject, tenant_id, body: ShareReviewInput) -> ShareReview:
        row = await self.reviews.conversation(subject, tenant_id, body, purpose="share")
        snapshot = stored_snapshot(row.snapshot_json)
        remembered = await self.reviews.memory_check(subject, tenant_id, snapshot)
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

    @transactional
    async def create(self, subject, tenant_id, body: ShareCreate) -> Share:
        self.reviews.settings.validate()
        await self.reviews.catalog._lock_tenant(tenant_id)
        if await self.shares.active_count(subject, tenant_id) >= self.reviews.settings.max_active_shares:
            raise ConflictException(
                "Revoke an existing share before creating another", code="SHARE_LIMIT_REACHED"
            )
        review = await self.reviews.claim(
            subject, tenant_id, body.review_id, body.expected_revision, purpose="share"
        )
        now = datetime.now(UTC)
        expires = now + timedelta(hours=body.expires_in_hours)
        snapshot = stored_snapshot(review.snapshot_json)
        await self.reviews.memory_check(
            subject,
            tenant_id,
            snapshot,
            transfer=True,
            consent=body.include_remembered_context,
            permission="shares:write",
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write",
        )
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
        await self.reviews.memory_check(
            subject,
            tenant_id,
            snapshot,
            transfer=True,
            consent=body.include_remembered_context,
            permission="shares:write",
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write",
        )
        return self._dto(row, review)

    @transactional(read_only=True, read_from_primary=True)
    async def read(self, subject, tenant_id, identifier) -> SharedConversation:
        rows = await self.shares.find_all(id=identifier, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
        row = rows[0]
        review, snapshot = await self._saved(subject, tenant_id, row)
        if row.revoked_at:
            raise GoneException("This share was revoked by its owner", code="SHARE_REVOKED")
        if row.expires_at <= datetime.now(UTC):
            raise GoneException("This share has expired", code="SHARE_EXPIRED")
        resolver = self.reviews.sources.get()
        if resolver is not None:
            snapshot = snapshot.model_copy(
                update={"sources": await resolver.resolve(subject, tenant_id, snapshot.sources)}
            )
        await self.reviews.memory_check(
            row.owner_subject,
            tenant_id,
            snapshot,
            transfer=True,
            consent=snapshot.memory_transfer_consented,
            reader_subject=subject,
            permission="shares:read",
            creator_token_id=review.creator_token_id,
            creator_permission="shares:write",
            release=("share", row.id),
        )
        await self.reviews.output_check(row.owner_subject, tenant_id, snapshot)
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
        review = await self.reviews.reviews.find_by_id(row.review_id)
        await self.reviews.access.management(
            subject,
            tenant_id,
            stored_snapshot(review.snapshot_json).sources,
            permission="shares:write",
        )
        if row.revoked_at is None:
            row.revoked_at = datetime.now(UTC)
            await self.shares.save(row)
            await self.reviews.catalog._audit(subject, tenant_id, "share.revoked", row.id)

    @transactional(read_only=True, read_from_primary=True)
    async def page(self, subject, tenant_id, **filters) -> SharePage:
        result = await self.shares.page(subject, tenant_id, **filters)
        items = []
        for row in result["items"]:
            review = await self.reviews.reviews.find_by_id(row.review_id)
            if review is None or review.tenant_id != tenant_id or review.owner_subject != subject:
                raise AccessDenied("This share is unavailable", code="SHARE_UNAVAILABLE")
            sources = tuple(SourceReference.model_validate(item) for item in review.manifest_json)
            await self.reviews.access.management(subject, tenant_id, sources, permission="shares:read")
            items.append(self._dto(row, review))
        if not items:
            await self.reviews.catalog.authorize(subject, tenant_id, "shares:read")
        return SharePage(**{**result, "items": items})
