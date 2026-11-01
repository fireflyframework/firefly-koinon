# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest
from pyfly.kernel import ConflictException, InvalidRequestException
from test_membership_events import communications as communications

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.communications.dtos import NotificationPreferencesInput
from koinon.communications.inbox import NotificationService

ACTOR = "https://issuer.test|admin"
OWNER = "https://issuer.test|person"


async def test_owner_inbox_survives_membership_loss_without_exposing_other_subjects(communications):
    catalog = communications.get_bean(CatalogService)
    member = await catalog.create_member(ACTOR, "north", subject=OWNER, role="viewer")
    await catalog.update_member(ACTOR, "north", member.id, active=False)
    inbox = communications.get_bean(NotificationService)
    page = await inbox.page(OWNER)
    assert page.total == 2 and {item.kind for item in page.items} == {"access_granted", "access_removed"}
    removed = next(item for item in page.items if item.kind == "access_removed")
    assert "role assignment" in removed.body and removed.target.kind == "none"
    assert (await inbox.page("https://issuer.test|other")).total == 0
    with pytest.raises(AccessDenied):
        await inbox.mark_read("https://issuer.test|other", removed.id)
    assert (await inbox.unread_count(OWNER)).unread == 2
    await inbox.mark_read(OWNER, removed.id)
    await inbox.mark_read(OWNER, removed.id)
    assert (await inbox.unread_count(OWNER)).unread == 1
    assert (await inbox.page(OWNER, read="unread")).total == 1


async def test_preferences_are_owner_revisioned_and_required_notice_channels_cannot_be_disabled(
    communications,
):
    inbox = communications.get_bean(NotificationService)
    initial = await inbox.preferences(OWNER)
    assert initial.revision == 0 and initial.digest == "off" and initial.time_zone == "UTC"
    body = NotificationPreferencesInput(
        expected_revision=0,
        digest="off",
        rules=[dict(kind=item.kind, inbox=item.inbox, email=item.email) for item in initial.rules],
    )
    result = await inbox.update_preferences(OWNER, body)
    assert result.revision == 1
    with pytest.raises(ConflictException):
        await inbox.update_preferences(OWNER, body)
    assert (await inbox.preferences("https://issuer.test|other")).revision == 0
    wrong = body.model_copy(
        update={
            "expected_revision": 1,
            "rules": [item.model_copy(update={"inbox": False}) for item in body.rules],
        }
    )
    with pytest.raises(InvalidRequestException):
        await inbox.update_preferences(OWNER, wrong)
