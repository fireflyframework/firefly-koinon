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


async def test_operator_only_contact_preview_uses_same_verified_target_without_directory(email_context):
    from test_operator_contacts import bind, contacts, observation
    from test_summary_rendering import activity_summary

    from koinon.catalog.service import CatalogService
    from koinon.communications.content import CommunicationContent
    from koinon.communications.recipients import RecipientService
    from koinon.communications.repositories import CommunicationPolicyRepository, RecipientIdentityRepository
    from koinon.communications.settings import CommunicationsSettings, InstallationLinks
    from koinon.communications.templates import EmailRenderer

    context, directory = email_context
    operator = await contacts(context)
    await operator.provision(observation())
    await bind(operator)
    summary = activity_summary()
    service = ActivityEmailPreviewService(
        context.get_bean(CommunicationContent),
        context.get_bean(RecipientService),
        context.get_bean(RecipientIdentityRepository),
        context.get_bean(OutboxRepository),
        context.get_bean(CommunicationPolicyRepository),
        context.get_bean(CommunicationsSettings),
        context.get_bean(InstallationLinks),
        context.get_bean(EmailRenderer),
        context.get_bean(CatalogService),
        SimpleNamespace(personal=AsyncMock(return_value=summary)),
        operator_contacts=operator,
    )
    body = ActivityEmailPreviewInput(
        tenant_id="north",
        window=summary.window,
        preferences=NotificationPreferencesInput(expected_revision=0, rules=[], digest="weekly"),
    )
    value = await service.preview(ACTOR, body)
    assert value.rendered_html and value.rendered_text and directory.reads == 0
    assert value.recipient_email == "approved@example.test"
    assert not await context.get_bean(OutboxRepository).find_all(kind="digest")
