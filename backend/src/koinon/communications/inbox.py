# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Subject-owned history survives membership loss; destinations retain current ACL checks."""

from typing import get_args
from zoneinfo import ZoneInfo

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException
from sqlalchemy import func, select

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.communications.calendar import digest_window, next_run
from koinon.communications.dtos import (
    DigestFrequency,
    DigestSchedule,
    DigestSchedulePreview,
    EventKind,
    NotificationPreferenceRule,
    NotificationPreferences,
    NotificationPreferencesInput,
    NotificationUnreadCount,
    OwnNotificationPage,
)
from koinon.communications.entities import CommunicationPolicyRecord, NotificationRecord
from koinon.communications.locale_service import CommunicationLocales
from koinon.communications.mappers import notification_dto
from koinon.communications.readiness import EmailReadiness
from koinon.communications.repositories import (
    NotificationPreferenceRepository,
    NotificationRepository,
    OutboxRepository,
)
from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.profiles.repositories import ProfileRepository
from koinon.profiles.service import profile_id
from koinon.security.authority import primary_authority
from koinon.web.pagination import sql_page

EVENT_KINDS = get_args(EventKind)


@service(name="communications.inbox")
class NotificationService:
    def __init__(
        self,
        notifications: NotificationRepository,
        preferences: NotificationPreferenceRepository,
        profiles: ProfileRepository,
        catalog: CatalogService,
        settings: CommunicationsSettings,
        links: InstallationLinks,
        outbox: OutboxRepository,
        locales: CommunicationLocales,
        readiness: EmailReadiness,
    ):
        self.notifications, self.preference_rows, self.profiles, self.catalog = (
            notifications,
            preferences,
            profiles,
            catalog,
        )
        self.settings, self.links, self.outbox = settings, links, outbox
        self.locales, self.readiness = locales, readiness

    async def _dto(self, owner, row):
        allowed = False
        if row.kind != "access_removed":
            allowed = "catalog:read" in await self.catalog.permissions(owner, row.tenant_id, row.workspace_id)
        locale, origin = await self.locales.resolve(owner=owner, tenant_id=row.tenant_id)
        event = await self.outbox.find_by_id(row.event_id)
        return notification_dto(
            row, can_navigate=allowed, locale=locale, locale_origin=origin, details=event.event_json
        )

    @primary_authority()
    async def page(self, owner, *, tenant_id=None, kind=None, read="all", page=1, page_size=25):
        if read not in {"all", "unread", "read"} or kind is not None and kind not in EVENT_KINDS:
            raise InvalidRequestException(
                "Choose supported notification filters", code="INVALID_NOTIFICATION_FILTER"
            )
        predicates = [NotificationRecord.owner_subject == owner]
        if tenant_id is not None:
            predicates.append(NotificationRecord.tenant_id == tenant_id)
        if kind is not None:
            predicates.append(NotificationRecord.kind == kind)
        if read != "all":
            predicates.append(
                NotificationRecord.read_at.is_(None)
                if read == "unread"
                else NotificationRecord.read_at.is_not(None)
            )
        rows = await sql_page(
            NotificationRecord, predicates, page=page, page_size=page_size, sorts=("created_at",)
        )
        return OwnNotificationPage(
            **{**rows, "items": [await self._dto(owner, row) for row in rows["items"]]}
        )

    @primary_authority()
    async def unread_count(self, owner):
        count = await self.notifications._require_session().scalar(
            select(func.count())
            .select_from(NotificationRecord)
            .where(NotificationRecord.owner_subject == owner, NotificationRecord.read_at.is_(None))
        )
        return NotificationUnreadCount(unread=int(count or 0))

    @transactional
    async def mark_read(self, owner, identifier):
        rows = await self.notifications.find_all(id=identifier, owner_subject=owner)
        if not rows:
            raise AccessDenied("This notification is unavailable", code="NOTIFICATION_UNAVAILABLE")
        row = await self.notifications.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row.read_at is None:
            row.read_at = await self.outbox.clock()
            await self.notifications.save(row)
        return await self._dto(owner, row)

    def _rules(self, stored, sender_id=None):
        values = {item["kind"]: item for item in stored}
        available = self.readiness.observe(sender_id=sender_id).state == "ready"
        return [
            NotificationPreferenceRule(
                kind=kind,
                required=kind != "digest",
                inbox=True if kind != "digest" else values.get(kind, {}).get("inbox", False),
                email=available
                if kind != "digest"
                else available and values.get(kind, {}).get("email", False),
                email_available=available,
            )
            for kind in EVENT_KINDS
        ]

    async def _digest_allowed(self, owner) -> list[DigestFrequency]:
        rows = self.catalog.effective_membership_rows()
        members = rows.c
        statement = (
            select(CommunicationPolicyRecord)
            .join(rows, members.tenant_id == CommunicationPolicyRecord.tenant_id)
            .where(
                members.subject == owner,
                members.active.is_(True),
                CommunicationPolicyRecord.digest_enabled.is_(True),
            )
            .distinct()
            .limit(101)
        )
        policies = list(await self.notifications._require_session().scalars(statement))
        if len(policies) > 100:
            raise InvalidRequestException(
                "Notification preferences exceed the bounded organization policy capacity",
                code="COMMUNICATION_POLICY_CAPACITY",
            )
        selected = {cadence for policy in policies for cadence in policy.allowed_digests_json}
        cadences: tuple[DigestFrequency, ...] = ("off", "daily", "weekly", "monthly")
        return [cadence for cadence in cadences if cadence == "off" or cadence in selected]

    async def _admin_available(self, owner):
        membership_rows = self.catalog.effective_membership_rows()
        rows = membership_rows.c
        values = list(
            await self.notifications._require_session().scalars(
                select(CommunicationPolicyRecord)
                .join(membership_rows, rows.tenant_id == CommunicationPolicyRecord.tenant_id)
                .where(
                    rows.subject == owner,
                    rows.active.is_(True),
                    rows.role == "admin",
                    rows.workspace_id.is_(None),
                )
                .distinct()
                .limit(101)
            )
        )
        if len(values) > 100:
            raise InvalidRequestException(
                "Notification policy capacity exceeded", code="COMMUNICATION_POLICY_CAPACITY"
            )
        return any(value.admin_summaries_json for value in values)

    @primary_authority()
    async def preferences(self, owner):
        row = await self.preference_rows.find_by_id(owner)
        profile = await self.profiles.find_by_id(profile_id(owner))
        allowed: list[DigestFrequency] = await self._digest_allowed(owner)
        locale, origin = await self.locales.resolve(owner=owner)
        schedule = DigestSchedule.model_validate(row.schedule_json if row else {})
        admin_available = await self._admin_available(owner)
        return NotificationPreferences(
            admin_summaries_available=admin_available,
            admin_summaries_enabled=admin_available and (row is None or row.admin_summaries is not False),
            revision=row.revision if row else 0,
            rules=self._rules(row.rules_json if row else []),
            digest=row.digest if row else "off",
            allowed_digests=allowed,
            locale=locale,
            time_zone=profile.time_zone if profile else "UTC",
            schedule=schedule,
            next_run_at=row.next_due_at if row else None,
            next_run_local=row.next_due_at.astimezone(
                ZoneInfo(profile.time_zone if profile else "UTC")
            ).isoformat()
            if row and row.next_due_at
            else None,
            notification_locale=row.notification_locale if row else None,
            admin_summaries=row.admin_summaries if row else None,
            effective_locale=locale,
            locale_origin=origin,
        )

    @transactional
    async def update_preferences(self, owner, body: NotificationPreferencesInput):
        body = NotificationPreferencesInput.model_validate(body)
        current = await self.preferences(owner)
        seen = {item.kind for item in body.rules}
        if len(seen) != len(body.rules) or body.digest not in current.allowed_digests:
            raise InvalidRequestException(
                "Choose supported notification preferences", code="INVALID_NOTIFICATION_PREFERENCES"
            )
        required = {item.kind: item for item in current.rules if item.required}
        for item in body.rules:
            if item.kind in required and (not item.inbox or required[item.kind].email and not item.email):
                raise InvalidRequestException(
                    "Required access notices cannot be disabled", code="REQUIRED_NOTIFICATION"
                )
        row = await self.preference_rows.find_by_id(owner)
        now = await self.outbox.clock()
        changed = (
            row is None
            or row.digest != body.digest
            or row.schedule_json != body.schedule.model_dump()
            or row.time_zone_snapshot != current.time_zone
        )
        due = (
            next_run(body.digest, body.schedule, current.time_zone, now)
            if changed or row is None
            else row.next_due_at
        )
        selected_locale = (
            body.notification_locale
            if "notification_locale" in body.model_fields_set
            else current.notification_locale
        )
        if not await self.preference_rows.compare_and_swap(
            owner,
            body.expected_revision,
            [item.model_dump() for item in body.rules],
            body.digest,
            schedule=body.schedule.model_dump(),
            notification_locale=selected_locale,
            next_due_at=due,
            cursor=now if changed or row is None else row.digest_cursor,
            time_zone=current.time_zone,
            admin_summaries=body.admin_summaries
            if "admin_summaries" in body.model_fields_set
            else current.admin_summaries,
        ):
            raise ConflictException(
                "Notification preferences changed; reload and try again",
                code="NOTIFICATION_PREFERENCES_CHANGED",
            )
        return await self.preferences(owner)

    @primary_authority()
    async def preview_schedule(self, owner, body: NotificationPreferencesInput):
        body = NotificationPreferencesInput.model_validate(body)
        current = await self.preferences(owner)
        if body.digest not in current.allowed_digests:
            raise InvalidRequestException(
                "Choose an allowed digest cadence", code="INVALID_NOTIFICATION_PREFERENCES"
            )
        due = next_run(body.digest, body.schedule, current.time_zone, await self.outbox.clock())
        start, end = (
            digest_window(body.digest, body.schedule, current.time_zone, due) if due else (None, None)
        )
        return DigestSchedulePreview(
            digest=body.digest,
            schedule=body.schedule,
            time_zone=current.time_zone,
            next_run_at=due,
            next_run_local=due.astimezone(ZoneInfo(current.time_zone)).isoformat() if due else None,
            window_start=start,
            window_end=end,
            effective_locale=current.effective_locale,
            locale_origin=current.locale_origin,
        )
