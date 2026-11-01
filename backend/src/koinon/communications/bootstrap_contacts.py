# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Operator-only contact observations do not create principals, credentials or administrator access."""

import json
from dataclasses import dataclass
from datetime import UTC, timedelta
from hashlib import sha256
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from sqlalchemy import select

from koinon.bootstrap.dtos import BootstrapContactInput
from koinon.bootstrap.entities import BootstrapIdentityGrant
from koinon.bootstrap.repositories import BootstrapGrantRepository
from koinon.catalog.entities import Membership
from koinon.communications.crypto import CommunicationsCipher
from koinon.communications.directory import DirectoryPerson
from koinon.communications.entities import BootstrapContactRecord, OutboxRecord, WelcomeAdmissionRecord
from koinon.communications.events import CommunicationEvents
from koinon.communications.repositories import BootstrapContactRepository, OutboxRepository
from koinon.communications.welcome import installation_identity
from koinon.security.authority import primary_authority
from koinon.security.settings import OidcSettings


def bootstrap_identity_key(tid, oid):
    return json.dumps(["entra", str(tid), str(oid)], separators=(",", ":"))


@dataclass(frozen=True, slots=True)
class PreparedBootstrapContact:
    id: str
    tenant_id: str
    person: DirectoryPerson


@service(name="communications.bootstrap_contacts")
class BootstrapContacts:
    def __init__(
        self,
        contacts: BootstrapContactRepository,
        grants: BootstrapGrantRepository,
        outbox: OutboxRepository,
        cipher: CommunicationsCipher,
        events: CommunicationEvents,
        oidc: OidcSettings,
    ):
        self.contacts, self.grants, self.outbox, self.cipher, self.events, self.oidc = (
            contacts,
            grants,
            outbox,
            cipher,
            events,
            oidc,
        )

    def _pins(self, value):
        return (
            value.issuer == self.oidc.issuer
            and value.client_id == self.oidc.client_id
            and value.issuer == f"https://login.microsoftonline.com/{value.entra_tenant_id}/v2.0"
        )

    @transactional
    async def admit(self, value: BootstrapContactInput):
        """Called only by the privileged operator command; runtime roles cannot insert contact rows."""
        if not self.events.settings.enabled:
            raise ValueError("Enable communications before operator contact admission")
        if not self._pins(value):
            raise ValueError("Contact must match the configured direct issuer and client")
        session = self.contacts._require_session()
        grant = await session.scalar(
            select(BootstrapIdentityGrant)
            .where(
                BootstrapIdentityGrant.tenant_id == value.tenant_id,
                BootstrapIdentityGrant.canonical_issuer == value.issuer,
                BootstrapIdentityGrant.native_client_id == value.client_id,
                BootstrapIdentityGrant.entra_tenant_id == str(value.entra_tenant_id),
                BootstrapIdentityGrant.object_id == str(value.object_id),
            )
            .with_for_update()
        )
        now = (await self.outbox.clock()).astimezone(UTC)
        observed_at = value.observed_at.astimezone(UTC)
        if grant is None or not now - timedelta(minutes=15) <= observed_at <= now + timedelta(seconds=30):
            raise ValueError("Contact requires a fresh observation of an existing exact bootstrap grant")
        installation = await installation_identity(session, now)
        identity = sha256(bootstrap_identity_key(value.entra_tenant_id, value.object_id).encode()).hexdigest()
        prior = await session.scalar(
            select(BootstrapContactRecord).where(
                BootstrapContactRecord.installation_id == installation.installation_id,
                BootstrapContactRecord.identity_sha256 == identity,
            )
        )
        if prior is not None:
            original = BootstrapContactInput.model_validate(
                self.cipher.open(value.tenant_id, "bootstrap_contact", prior.contact_ciphertext)
            )
            if prior.grant_id != grant.id or original.email != value.email:
                raise ValueError("An admitted bootstrap identity cannot be retargeted")
            return prior
        welcomed = await session.scalar(
            select(WelcomeAdmissionRecord.id).where(
                WelcomeAdmissionRecord.installation_id == installation.installation_id,
                WelcomeAdmissionRecord.immutable_identity_sha256 == identity,
            )
        )
        if welcomed is not None:
            raise ValueError("This immutable identity already has an installation welcome")
        if grant.consumed_at is not None or grant.expires_at <= now or grant.role != "admin":
            raise ValueError("Contact requires a current pending administrator grant")
        identifier, event_id = str(uuid4()), str(uuid4())
        tenant = await self.events.tenants.find_by_id(value.tenant_id)
        if tenant is None:
            raise ValueError("Bootstrap organization is unavailable")
        provenance = dict(organization_name=tenant.name, workspace_name=None, actor_name=None)
        ready = self.events.settings.enabled and await self.events.email_ready(value.tenant_id)
        await self.outbox.save(
            OutboxRecord(
                id=event_id,
                dedupe_key="bootstrap-welcome:" + installation.installation_id + ":" + identity,
                tenant_id=value.tenant_id,
                owner_subject=None,
                kind="welcome",
                event_json={**provenance, "bootstrap_contact_id": identifier, "bootstrap_pending": True},
                status="queued" if ready else "suppressed",
                failure_code=None if ready else "EMAIL_DISABLED",
                created_at=now,
                next_attempt_at=now,
                completed_at=None if ready else now,
            )
        )
        row = BootstrapContactRecord(
            id=identifier,
            installation_id=installation.installation_id,
            grant_id=grant.id,
            identity_sha256=identity,
            event_id=event_id,
            contact_ciphertext=self.cipher.seal(
                value.tenant_id, "bootstrap_contact", value.model_dump(mode="json")
            ),
            observed_at=observed_at,
            expires_at=min(grant.expires_at, observed_at + timedelta(hours=24)),
        )
        await self.contacts.save(row)
        return row

    async def _current(self, event, *, lock=False):
        session = self.contacts._require_session()
        query = select(BootstrapContactRecord)
        identifier = event.event_json.get("bootstrap_contact_id") if event.kind == "welcome" else None
        if identifier:
            query = query.where(
                BootstrapContactRecord.id == identifier, BootstrapContactRecord.event_id == event.id
            )
        else:
            return None
        if lock:
            query = query.with_for_update()
        rows = list(await session.scalars(query.limit(2)))
        if len(rows) != 1:
            return None
        row = rows[0]
        grant = await self.grants.find_by_id(row.grant_id)
        now = (await self.outbox.clock()).astimezone(UTC)
        if (
            grant is None
            or grant.tenant_id != event.tenant_id
            or row.expires_at <= now
            or grant.expires_at <= now
        ):
            return None
        value = BootstrapContactInput.model_validate(
            self.cipher.open(event.tenant_id, "bootstrap_contact", row.contact_ciphertext)
        )
        if (
            not self._pins(value)
            or grant.canonical_issuer != value.issuer
            or grant.native_client_id != value.client_id
            or grant.entra_tenant_id != str(value.entra_tenant_id)
            or grant.object_id != str(value.object_id)
        ):
            return None
        if row.canonical_subject is None:
            if event.owner_subject is not None or grant.consumed_at is not None or event.kind != "welcome":
                return None
        else:
            if row.canonical_subject != event.owner_subject or grant.consumed_subject != event.owner_subject:
                return None
            member = await session.scalar(
                select(Membership).where(
                    Membership.id == grant.membership_id,
                    Membership.subject == row.canonical_subject,
                    Membership.tenant_id == grant.tenant_id,
                    Membership.active.is_(True),
                    Membership.workspace_id.is_(None),
                    Membership.role == "admin",
                )
            )
            if member is None:
                return None
        return PreparedBootstrapContact(
            row.id,
            grant.tenant_id,
            DirectoryPerson(grant.object_id, value.display_name, value.email, "verified_directory"),
        )

    @primary_authority()
    async def prepare(self, event):
        return await self._current(event)

    async def validate(self, event, prepared):
        current = await self._current(event, lock=True)
        return current is not None and current == prepared
