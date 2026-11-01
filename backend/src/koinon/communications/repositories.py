# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from koinon.communications.entities import (
    BootstrapContactRecord,
    CommunicationPolicyRecord,
    EmailInvitationRecord,
    NotificationPreferenceRecord,
    NotificationRecord,
    OutboxRecord,
    RecipientIdentityRecord,
)


@repository(name="communications.bootstrap_contacts")
class BootstrapContactRepository(Repository[BootstrapContactRecord, str]):
    pass


@repository(name="communications.invitations")
class EmailInvitationRepository(Repository[EmailInvitationRecord, str]):
    pass


@repository(name="communications.identities")
class RecipientIdentityRepository(Repository[RecipientIdentityRecord, str]):
    pass


@repository(name="communications.outbox")
class OutboxRepository(Repository[OutboxRecord, str]):
    def clock_expression(self):
        return (
            func.clock_timestamp()
            if self._require_session().get_bind().dialect.name == "postgresql"
            else func.current_timestamp()
        )

    async def clock(self) -> datetime:
        value = await self._require_session().scalar(select(self.clock_expression()))
        if isinstance(value, str):
            value = datetime.fromisoformat(value)
        if not isinstance(value, datetime):
            raise RuntimeError("The native database clock is unavailable")
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value


@repository(name="communications.notifications")
class NotificationRepository(Repository[NotificationRecord, str]):
    pass


@repository(name="communications.preferences")
class NotificationPreferenceRepository(Repository[NotificationPreferenceRecord, str]):
    async def compare_and_swap(
        self,
        subject,
        revision,
        rules,
        digest,
        *,
        schedule=None,
        notification_locale=None,
        next_due_at=None,
        cursor=None,
        time_zone="UTC",
        admin_summaries=None,
    ):
        session = self._require_session()
        values = dict(
            revision=revision + 1,
            rules_json=rules,
            digest=digest,
            admin_summaries=admin_summaries,
            schedule_json=schedule or {},
            notification_locale=notification_locale,
            next_due_at=next_due_at,
            digest_cursor=cursor,
            time_zone_snapshot=time_zone,
        )
        if revision == 0:
            insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else postgres_insert
            statement = (
                insert(NotificationPreferenceRecord)
                .values(subject=subject, **values)
                .on_conflict_do_nothing(index_elements=["subject"])
                .returning(NotificationPreferenceRecord.subject)
            )
        else:
            statement = (
                update(NotificationPreferenceRecord)
                .where(
                    NotificationPreferenceRecord.subject == subject,
                    NotificationPreferenceRecord.revision == revision,
                )
                .values(**values)
                .returning(NotificationPreferenceRecord.subject)
            )
        return (await session.execute(statement)).scalar_one_or_none() is not None


@repository(name="communications.policies")
class CommunicationPolicyRepository(Repository[CommunicationPolicyRecord, str]):
    async def compare_and_swap(self, tenant_id, revision, values):
        session = self._require_session()
        values = {**values, "revision": revision + 1}
        if revision == 0:
            insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else postgres_insert
            statement = (
                insert(CommunicationPolicyRecord)
                .values(tenant_id=tenant_id, **values)
                .on_conflict_do_nothing(index_elements=["tenant_id"])
                .returning(CommunicationPolicyRecord.tenant_id)
            )
        else:
            statement = (
                update(CommunicationPolicyRecord)
                .where(
                    CommunicationPolicyRecord.tenant_id == tenant_id,
                    CommunicationPolicyRecord.revision == revision,
                )
                .values(**values)
                .returning(CommunicationPolicyRecord.tenant_id)
            )
        return (await session.execute(statement)).scalar_one_or_none() is not None
