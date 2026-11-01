# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from pyfly.data.relational.sqlalchemy import transactional
from sqlalchemy import select
from test_membership_events import communications as communications

from koinon.catalog.service import CatalogService
from koinon.communications.administration import CommunicationsAdministration
from koinon.communications.digest import DigestScheduler
from koinon.communications.dtos import (
    AdministrativeSummarySchedule,
    CommunicationPolicyInput,
    NotificationPreferencesInput,
)
from koinon.communications.entities import DigestSubscriptionRecord
from koinon.communications.inbox import NotificationService
from koinon.communications.repositories import (
    NotificationPreferenceRepository,
    OutboxRepository,
)


def scheduler(context):
    return DigestScheduler(
        context.get_bean(OutboxRepository),
        context.get_bean(
            __import__("koinon.communications.events", fromlist=["CommunicationEvents"]).CommunicationEvents
        ),
        context.get_bean(CatalogService),
        context.get_bean(NotificationPreferenceRepository),
    )


async def test_due_native_subscription_admits_one_window_and_disable_does_not_backfill(communications):
    admin = "https://issuer.test|admin"
    body = CommunicationPolicyInput(
        expected_revision=0,
        rules=[],
        digest_enabled=True,
        allowed_digests=["off", "daily"],
        admin_summaries=[AdministrativeSummarySchedule(cadence="daily")],
    )
    await communications.get_bean(CommunicationsAdministration).update_policy(admin, "north", body)
    queue = scheduler(communications)
    await queue.reconcile()
    repo = communications.get_bean(OutboxRepository)

    @transactional
    async def due():
        rows = list(await repo._require_session().scalars(select(DigestSubscriptionRecord)))
        assert len(rows) == 1 and rows[0].audience == "organization_administrators"
        row = rows[0]
        row.cursor_at = datetime.now(UTC) - timedelta(days=2)
        row.next_due_at = datetime.now(UTC) - timedelta(days=1)
        return row.id

    identifier = await due()
    assert await queue.admit_due() == 1
    assert await queue.admit_due() == 0
    deliveries = await repo.find_all(kind="digest")
    assert len(deliveries) == 1 and deliveries[0].event_json["audience"] == "organization_administrators"
    communications.get_bean(
        __import__("koinon.communications.readiness", fromlist=["EmailReadiness"]).EmailReadiness
    ).state = "not_configured"

    @transactional
    async def due_again():
        row = await repo._require_session().get(DigestSubscriptionRecord, identifier)
        row.next_due_at = datetime.now(UTC) - timedelta(seconds=1)

    await due_again()
    assert await queue.admit_due() == 0
    assert len(await repo.find_all(kind="digest")) == 1


async def test_explicit_personal_digest_email_opt_out_keeps_inbox_only_and_never_queues_mail(communications):
    from koinon.communications.repositories import NotificationRepository

    actor = "https://issuer.test|admin"
    await communications.get_bean(CommunicationsAdministration).update_policy(
        actor,
        "north",
        CommunicationPolicyInput(
            expected_revision=0, rules=[], digest_enabled=True, allowed_digests=["off", "daily"]
        ),
    )
    await communications.get_bean(NotificationService).update_preferences(
        actor,
        NotificationPreferencesInput(
            expected_revision=0, rules=[dict(kind="digest", inbox=True, email=False)], digest="daily"
        ),
    )
    queue = scheduler(communications)
    await queue.reconcile()
    repo = communications.get_bean(OutboxRepository)

    @transactional
    async def due():
        row = await repo._require_session().scalar(select(DigestSubscriptionRecord))
        row.cursor_at = datetime.now(UTC) - timedelta(days=2)
        row.next_due_at = datetime.now(UTC) - timedelta(days=1)

    await due()
    assert await queue.admit_due() == 1
    row = (await repo.find_all(kind="digest"))[0]
    assert row.status == "suppressed" and row.failure_code == "CHANNEL_PREFERENCE"
    assert len(await communications.get_bean(NotificationRepository).find_all(kind="digest")) == 1

    @transactional
    async def current():
        return await queue.current(row)

    assert not await current()
