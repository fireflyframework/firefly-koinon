# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.container.scanner import scan_package
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.kernel import ConflictException

from koinon.catalog.entities import Membership, Tenant
from koinon.catalog.repositories import MembershipRepository, TenantRepository
from koinon.evidence.dtos import ConversationMessage, ConversationSnapshot
from koinon.evidence.ports import ConversationSnapshotPort
from koinon.evidence.reviews import EvidenceReviews
from koinon.exports.dtos import ConversationExportInput
from koinon.sharing.dtos import ShareReviewInput


class SnapshotFixture:
    revision = "a" * 64
    private = False
    origin_tokens = ()

    async def snapshot(self, subject, tenant_id, thread_id, message_ids):
        return ConversationSnapshot(
            thread_id=thread_id,
            tenant_id=tenant_id,
            owner_subject=subject,
            title="Review this answer",
            revision=self.revision,
            source_manifest_complete=True,
            originating_token_ids=self.origin_tokens,
            messages=tuple(
                ConversationMessage(
                    id=id,
                    role="assistant",
                    text="Reviewed answer",
                    status="completed",
                    revision=self.revision,
                    private_derived=self.private,
                )
                for id in message_ids
            ),
        )


@pytest.fixture
async def reviews(tmp_path):
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "banner": {"mode": "off"},
                    "eda": {"provider": "memory"},
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "create",
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'reviews.db'}",
                        }
                    },
                }
            }
        )
    )
    snapshot = SnapshotFixture()
    context.container.register_instance(ConversationSnapshotPort, snapshot)
    for package in (
        "koinon.catalog",
        "koinon.profiles",
        "koinon.tokens",
        "koinon.evidence",
        "koinon.exports",
        "koinon.sharing",
    ):
        scan_package(package, context.container)
    await context.start()
    try:
        await context.get_bean(TenantRepository).save(Tenant(id="north", name="North"))
        await context.get_bean(MembershipRepository).save(
            Membership(id="owner", subject="owner", tenant_id="north", role="viewer")
        )
        yield context.get_bean(EvidenceReviews), snapshot, context
    finally:
        await context.stop()


async def test_review_claim_rechecks_snapshot_revision_and_is_single_use(reviews):
    service, snapshot, _ = reviews
    body = ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="json")
    review = await service.conversation("owner", "north", body, purpose="export")
    snapshot.revision = "b" * 64
    with pytest.raises(ConflictException):
        await service.claim("owner", "north", review.id, review.revision, purpose="export")
    snapshot.revision = "a" * 64
    await service.claim("owner", "north", review.id, review.revision, purpose="export")
    with pytest.raises(ConflictException):
        await service.claim("owner", "north", review.id, review.revision, purpose="export")


async def test_private_derived_share_content_is_blocked_before_persistence_but_owner_export_is_explicit(
    reviews,
):
    service, snapshot, _ = reviews
    snapshot.private = True
    with pytest.raises(ConflictException, match="private attachment"):
        await service.conversation(
            "owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]), purpose="share"
        )
    exported = await service.conversation(
        "owner",
        "north",
        ConversationExportInput(kind="conversation", thread_id="t", message_ids=["m"], format="markdown"),
        purpose="export",
    )
    assert exported.snapshot_json["messages"][0]["private_derived"] is True


async def test_expired_review_and_other_subject_cannot_be_claimed(reviews):
    from koinon.catalog.errors import AccessDenied
    from koinon.evidence.repositories import EvidenceReviewRepository

    service, _, context = reviews
    review = await service.conversation(
        "owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]), purpose="share"
    )
    with pytest.raises(AccessDenied):
        await service.claim("other", "north", review.id, review.revision, purpose="share")
    repo = context.get_bean(EvidenceReviewRepository)
    review.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await repo.save(review)
    with pytest.raises(ConflictException):
        await service.claim("owner", "north", review.id, review.revision, purpose="share")
