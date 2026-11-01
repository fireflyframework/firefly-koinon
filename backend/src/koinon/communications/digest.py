# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded native due-row admission commits the immutable window and delivery key together."""

from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from sqlalchemy import select

from koinon.catalog.service import CatalogService
from koinon.communications.calendar import digest_window, latest_run, next_run
from koinon.communications.dtos import AdministrativeSummarySchedule, DigestSchedule
from koinon.communications.entities import (
    CommunicationPolicyRecord,
    DigestSubscriptionRecord,
    NotificationRecord,
    OutboxRecord,
)
from koinon.communications.events import CommunicationEvents
from koinon.communications.repositories import NotificationPreferenceRepository, OutboxRepository
from koinon.profiles.service import profile_id


@service(name="communications.digest_scheduler")
class DigestScheduler:
    def __init__(
        self,
        outbox: OutboxRepository,
        events: CommunicationEvents,
        catalog: CatalogService,
        preferences: NotificationPreferenceRepository,
    ):
        self.outbox, self.events, self.catalog, self.preferences = outbox, events, catalog, preferences
        self._policy_cursor = ""

    @transactional
    async def reconcile(self):
        session = self.outbox._require_session()
        policies = list(
            await session.scalars(
                select(CommunicationPolicyRecord)
                .where(CommunicationPolicyRecord.tenant_id > self._policy_cursor)
                .order_by(CommunicationPolicyRecord.tenant_id)
                .limit(25)
            )
        )
        if not policies:
            self._policy_cursor = ""
            return
        now = await self.outbox.clock()
        for policy in policies:
            await self.catalog._lock_tenant(policy.tenant_id)
            rows = self.catalog.effective_membership_rows().c
            members = list(
                (
                    await session.execute(
                        select(rows.subject, rows.role, rows.workspace_id)
                        .where(rows.tenant_id == policy.tenant_id, rows.active.is_(True))
                        .distinct()
                        .limit(1001)
                    )
                ).all()
            )
            if len(members) > 1000:
                raise RuntimeError(
                    "Communications reconciliation requires an operator-reviewed "
                    "recipient capacity above 1000 assignments"
                )
            desired = {}
            for owner in sorted({row.subject for row in members}):
                preference = await self.preferences.find_by_id(owner)
                profile = (
                    await self.events.profiles.find_by_id(profile_id(owner)) if self.events.profiles else None
                )
                zone = profile.time_zone if profile else "UTC"
                if (
                    policy.digest_enabled
                    and preference
                    and preference.digest in policy.allowed_digests_json
                    and preference.digest != "off"
                ):
                    desired[(owner, "personal", preference.digest)] = (
                        DigestSchedule.model_validate(preference.schedule_json),
                        zone,
                        f"{policy.revision}:{preference.revision}",
                    )
                is_admin = any(
                    row.subject == owner and row.role == "admin" and row.workspace_id is None
                    for row in members
                )
                if (
                    is_admin
                    and (preference is None or preference.admin_summaries is not False)
                    and "audit:read" in await self.catalog.permissions(owner, policy.tenant_id)
                ):
                    for value in policy.admin_summaries_json:
                        selected = AdministrativeSummarySchedule.model_validate(value)
                        desired[(owner, "organization_administrators", selected.cadence)] = (
                            selected.schedule,
                            zone,
                            f"{policy.revision}:{preference.revision if preference else 0}",
                        )
            current = list(
                await session.scalars(
                    select(DigestSubscriptionRecord)
                    .where(DigestSubscriptionRecord.tenant_id == policy.tenant_id)
                    .with_for_update()
                )
            )
            mapped = {(row.owner_subject, row.audience, row.cadence): row for row in current}
            for key, row in mapped.items():
                if key not in desired and row.enabled:
                    row.enabled, row.next_due_at, row.revision = False, None, row.revision + 1
            for key, (schedule, zone, source_revision) in desired.items():
                row = mapped.get(key)
                if row is None:
                    session.add(
                        DigestSubscriptionRecord(
                            id=str(uuid4()),
                            owner_subject=key[0],
                            tenant_id=policy.tenant_id,
                            audience=key[1],
                            cadence=key[2],
                            schedule_json=schedule.model_dump(),
                            time_zone=zone,
                            source_revision=source_revision,
                            cursor_at=now,
                            next_due_at=next_run(key[2], schedule, zone, now),
                        )
                    )
                elif (
                    not row.enabled
                    or row.source_revision != source_revision
                    or row.schedule_json != schedule.model_dump()
                    or row.time_zone != zone
                ):
                    row.enabled, row.source_revision, row.schedule_json, row.time_zone = (
                        True,
                        source_revision,
                        schedule.model_dump(),
                        zone,
                    )
                    row.cursor_at, row.next_due_at, row.revision = (
                        now,
                        next_run(row.cadence, schedule, zone, now),
                        row.revision + 1,
                    )
        await session.flush()
        self._policy_cursor = policies[-1].tenant_id

    @transactional
    async def admit_due(self):
        session = self.outbox._require_session()
        now = await self.outbox.clock()
        rows = list(
            await session.scalars(
                select(DigestSubscriptionRecord)
                .where(
                    DigestSubscriptionRecord.enabled.is_(True), DigestSubscriptionRecord.next_due_at <= now
                )
                .order_by(DigestSubscriptionRecord.next_due_at, DigestSubscriptionRecord.id)
                .limit(10)
                .with_for_update(skip_locked=True)
            )
        )
        admitted = 0
        for row in rows:
            schedule = DigestSchedule.model_validate(row.schedule_json)
            due = latest_run(row.cadence, schedule, row.time_zone, now)
            start, end = digest_window(row.cadence, schedule, row.time_zone, due)
            start = max(start, row.cursor_at)
            row.next_due_at = next_run(row.cadence, schedule, row.time_zone, now)
            row.cursor_at = max(row.cursor_at, end)
            if start >= end or not await self.eligible(row):
                continue
            email, inbox = await self.channels(row)
            email_ready = email and await self.events.email_ready(row.tenant_id)
            if not email_ready and not inbox:
                continue
            identifier = str(uuid4())
            key = f"digest:{row.id}:{end.isoformat()}"
            await self.outbox.save(
                OutboxRecord(
                    id=identifier,
                    dedupe_key=key,
                    tenant_id=row.tenant_id,
                    owner_subject=row.owner_subject,
                    kind="digest",
                    status="queued" if email_ready else "suppressed",
                    failure_code=None if email_ready else "EMAIL_DISABLED" if email else "CHANNEL_PREFERENCE",
                    completed_at=None if email_ready else now,
                    event_json=dict(
                        subscription_id=row.id,
                        subscription_revision=row.revision,
                        audience=row.audience,
                        cadence=row.cadence,
                        window_start=start.isoformat(),
                        window_end=end.isoformat(),
                        time_zone=row.time_zone,
                        **await self.events.provenance(row.owner_subject, row.tenant_id, None),
                    ),
                    created_at=now,
                    next_attempt_at=now,
                )
            )
            if inbox:
                provenance = await self.events.provenance(row.owner_subject, row.tenant_id, None)
                await self.events.notifications.save(
                    NotificationRecord(
                        id=str(uuid4()),
                        event_id=identifier,
                        owner_subject=row.owner_subject,
                        tenant_id=row.tenant_id,
                        kind="digest",
                        organization_name=provenance["organization_name"],
                        created_at=now,
                    )
                )
            admitted += 1
        await session.flush()
        return admitted

    async def eligible(self, row):
        if not row.enabled:
            return False
        policy = await self.events.policies.find_by_id(row.tenant_id) if self.events.policies else None
        preference = await self.preferences.find_by_id(row.owner_subject)
        permissions = await self.catalog.permissions(row.owner_subject, row.tenant_id)
        members = await self.catalog.memberships(row.owner_subject)
        if row.audience == "organization_administrators":
            return bool(
                policy
                and any(value.get("cadence") == row.cadence for value in policy.admin_summaries_json)
                and (preference is None or preference.admin_summaries is not False)
                and "audit:read" in permissions
                and any(
                    member.tenant_id == row.tenant_id
                    and member.workspace_id is None
                    and member.role == "admin"
                    for member in members
                )
            )
        return bool(
            policy
            and policy.digest_enabled
            and preference
            and preference.digest == row.cadence
            and row.cadence in policy.allowed_digests_json
            and any(member.tenant_id == row.tenant_id for member in members)
        )

    async def channels(self, row):
        if row.audience == "organization_administrators":
            return True, False
        preference = await self.preferences.find_by_id(row.owner_subject)
        rule = (
            next((item for item in preference.rules_json if item.get("kind") == "digest"), None)
            if preference
            else None
        )
        return (bool(rule.get("email")), bool(rule.get("inbox"))) if rule is not None else (True, False)

    async def current(self, event):
        row = await self.outbox._require_session().get(
            DigestSubscriptionRecord, event.event_json.get("subscription_id")
        )
        return (
            row is not None
            and row.revision == event.event_json.get("subscription_revision")
            and await self.eligible(row)
            and (await self.channels(row))[0]
        )
