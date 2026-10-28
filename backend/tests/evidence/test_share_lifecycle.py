# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

import pytest
from pyfly.kernel import ConflictException, GoneException
from test_evidence_reviews import reviews as reviews

from koinon.catalog.entities import Membership
from koinon.catalog.errors import AccessDenied
from koinon.catalog.repositories import MembershipRepository
from koinon.sharing.dtos import ShareCreate, ShareReviewInput
from koinon.sharing.service import ConversationShares


async def test_authenticated_share_has_expiry_revoke_and_current_owner_membership_checks(reviews):
    _, _, context = reviews
    service = context.get_bean(ConversationShares)
    members = context.get_bean(MembershipRepository)
    await members.save(Membership(id="recipient", subject="recipient", tenant_id="north", role="viewer"))
    preview = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    assert preview.messages[0].text == "Reviewed answer" and preview.source_manifest_complete
    created = await service.create(
        "owner", "north", ShareCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    opened = await service.read("recipient", "north", created.id)
    assert opened.messages[0].text == "Reviewed answer" and opened.share.status == "active"
    with pytest.raises(AccessDenied):
        await service.read("foreign", "north", created.id)
    await service.revoke("owner", "north", created.id)
    with pytest.raises(GoneException):
        await service.read("recipient", "north", created.id)
    await service.revoke("owner", "north", created.id)


async def test_share_snapshot_is_frozen_and_review_reuse_is_rejected(reviews):
    _, snapshot, context = reviews
    service = context.get_bean(ConversationShares)
    preview = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    body = ShareCreate(review_id=preview.id, expected_revision=preview.revision)
    created = await service.create("owner", "north", body)
    snapshot.revision = "b" * 64
    assert (await service.read("owner", "north", created.id)).share.revision == preview.revision
    with pytest.raises(ConflictException):
        await service.create("owner", "north", body)


async def test_share_uses_server_filtering_and_expiry_does_not_depend_on_browser_clock(reviews):
    from koinon.sharing.repositories import ConversationShareRepository

    _, _, context = reviews
    service = context.get_bean(ConversationShares)
    for _ in range(3):
        preview = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
        await service.create(
            "owner", "north", ShareCreate(review_id=preview.id, expected_revision=preview.revision)
        )
    page = await service.page("owner", "north", q="Review", page=2, page_size=1)
    assert page.total == 3 and page.page == 2 and len(page.items) == 1
    assert (await service.page("owner", "north", q="missing")).total == 0
    repo = context.get_bean(ConversationShareRepository)
    row = await repo.find_by_id(page.items[0].id)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await repo.save(row)
    with pytest.raises(GoneException):
        await service.read("owner", "north", row.id)
    assert (await service.page("owner", "north", status="expired")).total == 1


async def test_shared_manifest_is_resolved_again_as_the_recipient_without_owner_impersonation(reviews):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.evidence.ports import SourceResolverPort

    _, _, context = reviews
    service = context.get_bean(ConversationShares)
    await context.get_bean(MembershipRepository).save(
        Membership(id="recipient", subject="recipient", tenant_id="north", role="viewer")
    )
    preview = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    created = await service.create(
        "owner", "north", ShareCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    resolver = SimpleNamespace(resolve=AsyncMock(return_value=()))
    context.container.register_instance(SourceResolverPort, resolver)
    await service.read("recipient", "north", created.id)
    resolver.resolve.assert_awaited_once_with("recipient", "north", ())


async def test_expired_state_is_disclosed_only_after_current_recipient_authorization(reviews):
    from pyfly.kernel import GoneException

    from koinon.sharing.repositories import ConversationShareRepository

    _, _, context = reviews
    service = context.get_bean(ConversationShares)
    preview = await service.preview("owner", "north", ShareReviewInput(thread_id="t", message_ids=["m"]))
    created = await service.create(
        "owner", "north", ShareCreate(review_id=preview.id, expected_revision=preview.revision)
    )
    repo = context.get_bean(ConversationShareRepository)
    row = await repo.find_by_id(created.id)
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await repo.save(row)
    with pytest.raises(GoneException) as error:
        await service.read("owner", "north", created.id)
    assert error.value.code == "SHARE_EXPIRED"
    with pytest.raises(AccessDenied):
        await service.read("foreign", "north", created.id)
