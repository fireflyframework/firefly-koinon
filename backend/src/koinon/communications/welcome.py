# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Installation identity and unique welcome admission do not depend on branding or release versions."""

from hashlib import sha256
from uuid import uuid4

from pyfly.container import bean, configuration, service
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from koinon.communications.entities import (
    InstallationRecord,
    NotificationRecord,
    OutboxRecord,
    WelcomeAdmissionRecord,
)
from koinon.communications.events import CommunicationEvents
from koinon.communications.ports import WelcomeAdmissionPort
from koinon.communications.repositories import OutboxRepository


@service(name="communications.welcome_admissions")
class WelcomeAdmissions:
    def __init__(self, outbox: OutboxRepository, events: CommunicationEvents):
        self.outbox, self.events = outbox, events

    async def admit(self, owner, tenant_id):
        if not self.events.settings.enabled:
            return None
        self.events.require_mutation()
        session = self.outbox._require_session()
        now = await self.outbox.clock()
        insert = sqlite_insert if session.get_bind().dialect.name == "sqlite" else postgres_insert
        await session.execute(
            insert(InstallationRecord)
            .values(singleton="installation", installation_id=str(uuid4()), created_at=now)
            .on_conflict_do_nothing(index_elements=["singleton"])
        )
        installation = await session.scalar(
            select(InstallationRecord).where(InstallationRecord.singleton == "installation").with_for_update()
        )
        prior = await session.scalar(
            select(WelcomeAdmissionRecord).where(
                WelcomeAdmissionRecord.installation_id == installation.installation_id,
                WelcomeAdmissionRecord.owner_subject == owner,
            )
        )
        if prior is not None:
            return prior
        identifier = str(uuid4())
        provenance = await self.events.provenance(owner, tenant_id, None)
        ready = await self.events.email_ready(tenant_id)
        await self.outbox.save(
            OutboxRecord(
                id=identifier,
                dedupe_key="welcome:"
                + installation.installation_id
                + ":"
                + sha256(owner.encode()).hexdigest(),
                tenant_id=tenant_id,
                owner_subject=owner,
                kind="welcome",
                event_json=provenance,
                status="suppressed",
                failure_code="DELIVERY_IDENTITY_UNVERIFIED" if ready else "EMAIL_DISABLED",
                created_at=now,
                next_attempt_at=now,
                completed_at=now,
            )
        )
        await self.events.notifications.save(
            NotificationRecord(
                id=str(uuid4()),
                event_id=identifier,
                owner_subject=owner,
                tenant_id=tenant_id,
                kind="welcome",
                organization_name=provenance["organization_name"],
                created_at=now,
            )
        )
        row = WelcomeAdmissionRecord(
            id=str(uuid4()),
            installation_id=installation.installation_id,
            owner_subject=owner,
            tenant_id=tenant_id,
            event_id=identifier,
            created_at=now,
        )
        session.add(row)
        await session.flush()
        return row

    async def bind(self, owner, tenant_id, identity_key):
        self.events.require_mutation()
        session = self.outbox._require_session()
        digest = sha256(identity_key.encode()).hexdigest()
        rows = list(
            await session.scalars(
                select(WelcomeAdmissionRecord)
                .where(
                    WelcomeAdmissionRecord.owner_subject == owner,
                    WelcomeAdmissionRecord.tenant_id == tenant_id,
                )
                .with_for_update()
            )
        )
        for row in rows:
            if row.immutable_identity_sha256 is not None:
                continue
            await session.scalar(
                select(InstallationRecord)
                .where(InstallationRecord.installation_id == row.installation_id)
                .with_for_update()
            )
            existing = await session.scalar(
                select(WelcomeAdmissionRecord).where(
                    WelcomeAdmissionRecord.installation_id == row.installation_id,
                    WelcomeAdmissionRecord.immutable_identity_sha256 == digest,
                )
            )
            event = await self.outbox.find_by_id(row.event_id)
            row.immutable_identity_sha256 = digest if existing is None else None
            if event.status == "suppressed" and event.failure_code == "DELIVERY_IDENTITY_UNVERIFIED":
                event.status = (
                    "queued"
                    if existing is None and await self.events.email_ready(tenant_id)
                    else "suppressed"
                )
                event.failure_code = (
                    None
                    if event.status == "queued"
                    else "WELCOME_ALREADY_ADMITTED"
                    if existing
                    else "EMAIL_DISABLED"
                )
                event.completed_at = None if event.status == "queued" else await self.outbox.clock()
                await self.outbox.save(event)
        await session.flush()


@configuration
class WelcomeConfiguration:
    @bean(name="communications.welcome_port")
    def welcome_port(self, admissions: WelcomeAdmissions) -> WelcomeAdmissionPort:
        return admissions
