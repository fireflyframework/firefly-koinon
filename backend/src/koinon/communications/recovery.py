# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit fresh deliveries retain the original welcome's outcome and automatic admission."""

import json
from dataclasses import dataclass, field
from datetime import UTC, timedelta
from hashlib import sha256
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import select

from koinon.catalog.entities import AuditEvent
from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.communications.bootstrap_contacts import BootstrapContacts
from koinon.communications.contact_dtos import OperatorContactInput
from koinon.communications.crypto import CommunicationsCipher
from koinon.communications.directory import DirectoryPerson
from koinon.communications.entities import OutboxRecord
from koinon.communications.operator_contacts import ACTOR, OperatorContacts, digest
from koinon.communications.recipients import recipient_unavailable
from koinon.communications.recovery_dtos import WelcomeRecoveryAcknowledgement, WelcomeRecoveryInput
from koinon.communications.recovery_entities import WelcomeRecoveryRecord
from koinon.communications.recovery_repository import WelcomeRecoveryRepository
from koinon.communications.repositories import OutboxRepository
from koinon.security.authority import primary_authority


@dataclass(frozen=True, slots=True)
class PreparedWelcomeRecovery:
    id: str
    tenant_id: str
    contact_revision: int
    person: DirectoryPerson = field(repr=False)


@service(name="communications.welcome_recovery")
class WelcomeRecoveryService:
    def __init__(
        self,
        records: WelcomeRecoveryRepository,
        operator_contacts: OperatorContacts,
        bootstrap_contacts: BootstrapContacts,
        outbox: OutboxRepository,
        catalog: CatalogService,
        cipher: CommunicationsCipher,
    ):
        self.records, self.operator_contacts, self.bootstrap_contacts = (
            records,
            operator_contacts,
            bootstrap_contacts,
        )
        self.outbox, self.catalog, self.cipher = outbox, catalog, cipher

    async def _original(self, identifier, *, lock=False):
        row = await self.outbox.find_by_id(
            identifier, **({"lock": LockMode.PESSIMISTIC_WRITE} if lock else {})
        )
        if row is None or row.kind != "welcome" or row.event_json.get("welcome_recovery_id"):
            raise recipient_unavailable()
        return row

    async def _administrator(self, actor, tenant_id, token_id=None):
        issuer, separator, subject = actor.partition("|")
        if not separator or not subject:
            raise recipient_unavailable()
        attributes = {"iss": issuer, "sub": subject}
        if token_id:
            if self.catalog.restriction is None:
                raise recipient_unavailable()
            attributes["koinon_token_id"] = token_id
        with SecurityContextHolder.using(SecurityContext(user_id=subject, attributes=attributes)):
            await self.catalog.authorize(actor, tenant_id, "members:write")
            grant = await self.catalog.restriction.grant(actor) if self.catalog.restriction else None
            if grant is not None and any(
                getattr(grant, key, None) is not None
                for key in ("workspace_ids", "asset_ids", "resource_ids")
            ):
                raise recipient_unavailable()
            if not await self.operator_contacts._admin(actor, tenant_id):
                raise recipient_unavailable()

    async def _recipient(self, original, contact_id, revision, *, prelogin, lock=False):
        contact = await self.operator_contacts.contacts.find_by_id(
            contact_id, **({"lock": LockMode.PESSIMISTIC_WRITE} if lock else {})
        )
        now = (await self.outbox.clock()).astimezone(UTC)
        if (
            contact is None
            or contact.tenant_id != original.tenant_id
            or contact.revision != revision
            or contact.revoked_at is not None
            or contact.expires_at <= now
        ):
            raise recipient_unavailable()
        value = OperatorContactInput.model_validate(
            self.cipher.open(original.tenant_id, "operator_contact", contact.contact_ciphertext)
        )
        if (
            value.identity.model_dump(mode="json") != contact.identity_json
            or value.expires_at != contact.expires_at
            or value.observed_at != contact.observed_at
            or contact.expires_at
            > contact.observed_at
            + timedelta(days=self.operator_contacts.settings.operator_contact_max_lifetime_days)
            or not self.operator_contacts._pins(value.identity)
            or digest(contact.identity_json) != contact.identity_key
        ):
            raise recipient_unavailable()
        if not prelogin:
            if (
                not original.owner_subject
                or not await self.operator_contacts._admin(original.owner_subject, original.tenant_id)
                or await self.operator_contacts._current(contact, original) is None
            ):
                raise recipient_unavailable()
        else:
            identifier = original.event_json.get("bootstrap_contact_id")
            old = await self.bootstrap_contacts.contacts.find_by_id(identifier) if identifier else None
            grant = await self.bootstrap_contacts.grants.find_by_id(old.grant_id) if old else None
            if (
                old is None
                or old.event_id != original.id
                or grant is None
                or grant.tenant_id != original.tenant_id
                or grant.role != "admin"
                or grant.consumed_at is not None
                or grant.expires_at <= now
                or contact.canonical_subject is not None
                or original.owner_subject is not None
            ):
                raise recipient_unavailable()
            identity = value.identity
            original_contact = self.cipher.open(
                original.tenant_id, "bootstrap_contact", old.contact_ciphertext
            )
            if (
                identity.kind != "entra"
                or identity.identity_mode != "direct"
                or identity.issuer != grant.canonical_issuer
                or identity.client_id != grant.native_client_id
                or identity.external_tenant_id != grant.entra_tenant_id
                or identity.external_subject != grant.object_id
                or value.email != original_contact["email"]
            ):
                raise recipient_unavailable()
        if original.payload_ciphertext:
            saved = self.cipher.open(original.tenant_id, "delivery", original.payload_ciphertext)
            encoded = json.dumps(saved, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
            if (
                saved["to"] != value.email
                or saved.get("id") != original.id
                or sha256(encoded).hexdigest() != original.payload_hash
            ):
                raise recipient_unavailable()
        return PreparedWelcomeRecovery(
            contact_id,
            original.tenant_id,
            revision,
            DirectoryPerson(
                value.identity.external_subject, value.display_name, value.email, "verified_directory"
            ),
        )

    async def _ack(self, row):
        delivery = await self.outbox.find_by_id(row.delivery_id)
        return WelcomeRecoveryAcknowledgement(
            original_delivery_id=row.original_delivery_id, delivery_id=row.delivery_id, status=delivery.status
        )

    async def operator_recover(self, identifier, body: WelcomeRecoveryInput, request_key):
        return await self._admit(None, identifier, body, request_key, operator=True)

    async def recover(self, actor, tenant_id, identifier, body: WelcomeRecoveryInput, request_key):
        original = await self._original(identifier)
        if original.tenant_id != tenant_id:
            raise recipient_unavailable()
        return await self._admit(actor, identifier, body, request_key, operator=False)

    @transactional(datasource="primary")
    async def _admit(self, actor, identifier, body, request_key, *, operator):
        body = WelcomeRecoveryInput.model_validate(body)
        if (
            not isinstance(request_key, str)
            or not 1 <= len(request_key) <= 64
            or any(ord(c) < 33 or ord(c) > 126 for c in request_key)
        ):
            raise InvalidRequestException(
                "Provide a bounded Idempotency-Key", code="WELCOME_RECOVERY_IDEMPOTENCY_REQUIRED"
            )
        original = await self._original(identifier)
        await self.catalog._lock_tenant(original.tenant_id)
        original = (
            await self.records.original_snapshot(identifier)
            if operator
            else await self.outbox.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        )
        if original is None or original.kind != "welcome" or original.event_json.get("welcome_recovery_id"):
            raise recipient_unavailable()
        context = SecurityContextHolder.get_context()
        token_id = context.attributes.get("koinon_token_id") if context else None
        if operator:
            await self.operator_contacts._operator()
            actor = ACTOR
        else:
            await self._administrator(actor, original.tenant_id, token_id)
        key = sha256(request_key.encode()).hexdigest()
        fingerprint = digest([actor, operator, identifier, body.model_dump(mode="json")])
        prior = await self.records.find_all(tenant_id=original.tenant_id, request_key=key)
        if prior:
            if prior[0].request_hash != fingerprint:
                raise ConflictException(
                    "The recovery request key was already used", code="WELCOME_RECOVERY_REQUEST_CONFLICT"
                )
            return await self._ack(prior[0])
        if original.generation != body.expected_generation or original.status not in {
            "unknown",
            "failed",
            "suppressed",
            "sent",
            "delivered",
        }:
            raise ConflictException("Reload the current welcome delivery", code="WELCOME_RECOVERY_CHANGED")
        await self._recipient(
            original,
            body.contact_id,
            body.expected_contact_revision,
            prelogin=original.owner_subject is None and operator,
            lock=True,
        )
        now = (await self.outbox.clock()).astimezone(UTC)
        recent = await self.records._require_session().scalar(
            select(WelcomeRecoveryRecord.id)
            .where(
                WelcomeRecoveryRecord.original_delivery_id == identifier,
                WelcomeRecoveryRecord.created_at > now - timedelta(minutes=5),
            )
            .limit(1)
        )
        if recent:
            raise ConflictException(
                "Wait five minutes before another manual welcome", code="WELCOME_RECOVERY_THROTTLED"
            )
        await self._ready(original.tenant_id)
        original = await self.records.original_snapshot(identifier)
        if original is None or original.generation != body.expected_generation:
            raise ConflictException("Reload the current welcome delivery", code="WELCOME_RECOVERY_CHANGED")
        identifier_new, delivery_id = str(uuid4()), str(uuid4())
        event = OutboxRecord(
            id=delivery_id,
            dedupe_key="welcome-recovery:" + identifier_new,
            tenant_id=original.tenant_id,
            owner_subject=original.owner_subject,
            kind="welcome",
            event_json={
                "welcome_recovery_id": identifier_new,
                "organization_name": original.event_json.get("organization_name"),
                "workspace_name": None,
                "actor_name": None,
                "bootstrap_pending": original.owner_subject is None,
            },
            status="queued",
            created_at=now,
            next_attempt_at=now,
        )
        await self.outbox.save(event)
        row = await self.records.save(
            WelcomeRecoveryRecord(
                id=identifier_new,
                tenant_id=original.tenant_id,
                original_delivery_id=original.id,
                original_generation=original.generation,
                delivery_id=delivery_id,
                contact_id=body.contact_id,
                contact_revision=body.expected_contact_revision,
                request_key=key,
                request_hash=fingerprint,
                authority_kind="operator" if operator else "administrator",
                requested_by=actor,
                origin_token_id=None if operator else token_id,
                reason=body.reason,
                created_at=now,
            )
        )
        await self.operator_contacts.audits.save(
            AuditEvent(
                id=str(uuid4()),
                tenant_id=original.tenant_id,
                subject=actor,
                action="communications.welcome.recovery_requested",
                resource_id=delivery_id,
                details={
                    "original_delivery_id": original.id,
                    "recovery_id": row.id,
                    "reason": body.reason,
                    "possible_original_late_arrival": True,
                },
            )
        )
        return await self._ack(row)

    async def _ready(self, tenant_id):
        policy = await self.operator_contacts.policies.find_by_id(tenant_id)
        self.operator_contacts.readiness.require_ready(sender_id=policy.sender_id if policy else None)

    async def _prepared(self, event, *, lock=False):
        row = await self.records.find_by_id(event.event_json.get("welcome_recovery_id"))
        if (
            row is None
            or row.delivery_id != event.id
            or row.tenant_id != event.tenant_id
            or event.kind != "welcome"
        ):
            return None
        if row.authority_kind == "administrator":
            await self._administrator(row.requested_by, row.tenant_id, row.origin_token_id)
        original = await self._original(row.original_delivery_id, lock=lock)
        if (
            original.tenant_id != event.tenant_id
            or original.generation != row.original_generation
            or original.owner_subject != event.owner_subject
        ):
            return None
        return await self._recipient(
            original,
            row.contact_id,
            row.contact_revision,
            prelogin=original.owner_subject is None and row.authority_kind == "operator",
            lock=lock,
        )

    @primary_authority()
    async def prepare(self, event):
        return await self._prepared(event)

    async def validate(self, event, prepared):
        try:
            return await self._prepared(event, lock=True) == prepared
        except AccessDenied:
            return False

    @primary_authority(fresh=True)
    async def recovery_options(self, actor, tenant_id, identifier):
        await self._administrator(actor, tenant_id, self._current_token())
        original = await self._original(identifier)
        if original.tenant_id != tenant_id:
            raise recipient_unavailable()
        if original.owner_subject is None:
            return None, "WELCOME_RECOVERY_OPERATOR_REQUIRED"
        rows = await self.operator_contacts.contacts.bound_candidates(tenant_id, original.owner_subject)
        if len(rows) != 1:
            return None, "WELCOME_RECOVERY_CONTACT_UNAVAILABLE"
        row = rows[0]
        try:
            await self._recipient(original, row.id, row.revision, prelogin=False)
        except AccessDenied:
            return None, "WELCOME_RECOVERY_CONTACT_UNAVAILABLE"
        if original.status not in {"unknown", "failed", "suppressed", "sent", "delivered"}:
            return None, "WELCOME_RECOVERY_CHANGED"
        now = (await self.outbox.clock()).astimezone(UTC)
        recent = await self.records._require_session().scalar(
            select(WelcomeRecoveryRecord.id)
            .where(
                WelcomeRecoveryRecord.original_delivery_id == original.id,
                WelcomeRecoveryRecord.created_at > now - timedelta(minutes=5),
            )
            .limit(1)
        )
        if recent:
            return None, "WELCOME_RECOVERY_THROTTLED"
        await self._ready(tenant_id)
        return row, None

    @staticmethod
    def _current_token():
        context = SecurityContextHolder.get_context()
        return context.attributes.get("koinon_token_id") if context else None

    @primary_authority(fresh=True)
    async def operator_status(self, identifier, contact_id):
        await self.operator_contacts._operator()
        original = await self._original(identifier)
        contact = await self.operator_contacts.contacts.find_by_id(contact_id)
        reason = None
        try:
            if contact is None:
                raise recipient_unavailable()
            await self._recipient(
                original, contact_id, contact.revision, prelogin=original.owner_subject is None
            )
            await self._ready(original.tenant_id)
            if original.status not in {"unknown", "failed", "suppressed", "sent", "delivered"}:
                reason = "WELCOME_RECOVERY_CHANGED"
        except (AccessDenied, ServiceUnavailableException) as error:
            reason = error.code
        recent = await self.records._require_session().scalar(
            select(WelcomeRecoveryRecord.id)
            .where(
                WelcomeRecoveryRecord.original_delivery_id == original.id,
                WelcomeRecoveryRecord.created_at
                > (await self.outbox.clock()).astimezone(UTC) - timedelta(minutes=5),
            )
            .limit(1)
        )
        if reason is None and recent:
            reason = "WELCOME_RECOVERY_THROTTLED"
        return {
            "delivery_id": original.id,
            "generation": original.generation,
            "submission_status": original.status,
            "attempt_count": original.attempt_count,
            "contact_id": contact_id,
            "contact_revision": contact.revision if contact else None,
            "can_recover_welcome": reason is None,
            "reason_code": reason,
            "possible_original_late_arrival": True,
        }
