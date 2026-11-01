# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.kernel import InvalidRequestException
from test_controller_guards import request
from test_email_invitations import ACTOR
from test_email_invitations import email_context as email_context

from koinon.activity.dtos import ActivityWindow
from koinon.catalog.errors import AccessDenied
from koinon.communications.controllers import NotificationController
from koinon.communications.dtos import ActivityEmailPreviewInput, NotificationPreferencesInput
from koinon.communications.preview import ActivityEmailPreviewService
from koinon.communications.repositories import OutboxRepository


async def test_activity_email_preview_requires_both_explicit_personal_scopes_before_aggregation():
    reader = SimpleNamespace(preview=AsyncMock(return_value="preview"))
    controller = NotificationController(None, reader)
    with pytest.raises(AccessDenied):
        await controller.email_preview(None, request(["notifications:read"]))
    reader.preview.assert_not_awaited()
    assert await controller.email_preview(None, request(["notifications:read", "activity:read"])) == "preview"
    assert reader.preview.await_args.args[0] == "https://issuer.test|owner"


async def test_future_preview_window_is_rejected_using_native_database_clock_without_writes(email_context):
    context, _ = email_context
    repo = context.get_bean(OutboxRepository)
    service = ActivityEmailPreviewService(
        None, None, None, repo, None, None, None, None, None, SimpleNamespace(personal=AsyncMock())
    )
    now = datetime.now(UTC)
    body = ActivityEmailPreviewInput(
        tenant_id="north",
        preferences=NotificationPreferencesInput(expected_revision=0, rules=[], digest="weekly"),
        window=ActivityWindow(start_at=now, end_at=now + timedelta(days=1), time_zone="UTC"),
    )
    with pytest.raises(InvalidRequestException) as failure:
        await service.preview(ACTOR, body)
    assert failure.value.code == "ACTIVITY_PREVIEW_FUTURE"
    service.summaries.personal.assert_not_awaited()
    assert not await repo.find_all(kind="digest")
