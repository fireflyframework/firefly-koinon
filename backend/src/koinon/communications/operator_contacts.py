# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Independent, operator-approved delivery targets with signed canonical identity binding."""

import json
from dataclasses import dataclass, field
from datetime import UTC, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import Isolation, LockMode, transactional
from pyfly.kernel import ConflictException
from sqlalchemy import select, text

from koinon.bootstrap.repositories import BootstrapGrantRepository
from koinon.catalog.entities import AuditEvent
from koinon.catalog.repositories import AuditRepository
from koinon.catalog.service import CatalogService
from koinon.communications.contact_dtos import ContactIdentity, OperatorContactInput
from koinon.communications.contact_entities import OperatorContactRecord
from koinon.communications.contact_repository import OperatorContactRepository
from koinon.communications.crypto import CommunicationsCipher
from koinon.communications.directory import DirectoryPerson
from koinon.communications.entities import OutboxRecord
from koinon.communications.readiness import EmailReadiness
from koinon.communications.recipients import recipient_unavailable
from koinon.communications.repositories import CommunicationPolicyRepository, OutboxRepository
from koinon.communications.settings import CommunicationsSettings
from koinon.corporate_identity.policy import verified_identity
from koinon.security.authority import primary_authority
from koinon.security.settings import OidcSettings

ACTOR = "system:communications-operator"


def digest(value) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class PreparedOperatorContact:
    id: str
    tenant_id: str
    owner: str
    revision: int
    configuration_sha256: str
    person: DirectoryPerson = field(repr=False)


@service(name="communications.operator_delivery_contacts")
class OperatorContacts:
    def __init__(
        self,
        contacts: OperatorContactRepository,
        outbox: OutboxRepository,
        cipher: CommunicationsCipher,
        catalog: CatalogService,
        audits: AuditRepository,
        oidc: OidcSettings,
        readiness: EmailReadiness,
        policies: CommunicationPolicyRepository,
        settings: CommunicationsSettings,
        bootstrap_grants: BootstrapGrantRepository | None = None,
    ):
        self.contacts, self.outbox, self.cipher = contacts, outbox, cipher
        self.catalog, self.audits, self.oidc = catalog, audits, oidc
        self.readiness, self.policies, self.bootstrap_grants = readiness, policies, bootstrap_grants
        self.settings = settings

    async def _now(self):
        return (await self.outbox.clock()).astimezone(UTC)

    def configuration_sha256(self):
        return digest([self.oidc.issuer, self.oidc.client_id])

    def _pins(self, identity):
        return identity.issuer == self.oidc.issuer and identity.client_id == self.oidc.client_id

    async def _operator(self):
        session = self.contacts._require_session()
        if session.get_bind().dialect.name == "postgresql" and not await session.scalar(
            text(
                "SELECT has_table_privilege(current_user,"
                "'public.koinon_operator_delivery_contacts','INSERT') "
                "AND has_column_privilege(current_user,'public.koinon_operator_delivery_contacts',"
                "'revision','UPDATE')"
            )
        ):
            raise recipient_unavailable()

    async def _admin(self, owner, tenant_id):
        now = await self._now()
        return any(
            row.tenant_id == tenant_id
            and row.workspace_id is None
            and row.role == "admin"
            and (getattr(row, "expires_at", None) is None or row.expires_at > now)
            for row in await self.catalog.memberships(owner)
        )

    async def _audit(self, row, action, details=None, *, actor=ACTOR):
        await self.audits.save(
            AuditEvent(
                id=str(uuid4()),
                tenant_id=row.tenant_id,
                subject=actor,
                action="communications.contact." + action,
                resource_id=row.id,
                details={"revision": row.revision, **(details or {})},
            )
        )

    async def _observation(self, value):
        now = (await self._now()).astimezone(UTC)
        observed = value.observed_at.astimezone(UTC)
        expires = value.expires_at.astimezone(UTC)
        if (
            not self._pins(value.identity)
            or not now - timedelta(minutes=15) <= observed <= now + timedelta(seconds=30)
            or not now
            < expires
            <= observed + timedelta(days=self.settings.operator_contact_max_lifetime_days)
        ):
            raise ValueError(
                "Contact needs current identity pins, a fresh observation "
                "and an expiry within installation policy"
            )
        if await self.catalog.tenant_repository.find_by_id(value.tenant_id) is None:
            raise ValueError("Contact organization is unavailable")
        return now, observed, expires

    def _seal_binding(self, row, owner):
        return self.cipher.seal(
            row.tenant_id,
            "operator_contact_binding",
            {
                "contact_id": row.id,
                "identity_key": row.identity_key,
                "subject": owner,
                "configuration_sha256": self.configuration_sha256(),
            },
        )

    @transactional(datasource="primary", isolation=Isolation.SERIALIZABLE)
    async def provision(self, value: OperatorContactInput):
        await self._operator()
        await self.catalog._lock_tenant(value.tenant_id)
        now, observed, expires = await self._observation(value)
        identity = value.identity.model_dump(mode="json")
        key = digest(identity)
        prior = await self.contacts.find_all(tenant_id=value.tenant_id, identity_key=key)
        if prior:
            saved = self.cipher.open(value.tenant_id, "operator_contact", prior[0].contact_ciphertext)
            if saved != value.model_dump(mode="json"):
                raise ConflictException(
                    "Renew the current contact explicitly with its revision", code="CONTACT_EXISTS"
                )
            return prior[0]
        row = OperatorContactRecord(
            id=str(uuid4()),
            tenant_id=value.tenant_id,
            identity_key=key,
            identity_json=identity,
            contact_ciphertext=self.cipher.seal(
                value.tenant_id, "operator_contact", value.model_dump(mode="json")
            ),
            revision=1,
            created_at=now,
            observed_at=observed,
            expires_at=expires,
        )
        if (
            self.bootstrap_grants
            and value.identity.kind == "entra"
            and value.identity.identity_mode == "direct"
        ):
            grants = await self.bootstrap_grants.find_all(
                tenant_id=value.tenant_id,
                canonical_issuer=value.identity.issuer,
                native_client_id=value.identity.client_id,
                entra_tenant_id=value.identity.external_tenant_id,
                object_id=value.identity.external_subject,
            )
            owners = {
                grant.consumed_subject for grant in grants if grant.consumed_at and grant.consumed_subject
            }
            if len(owners) == 1 and await self._admin(next(iter(owners)), row.tenant_id):
                row.canonical_subject = next(iter(owners))
                row.binding_ciphertext = self._seal_binding(row, row.canonical_subject)
                row.bound_at = next(
                    grant.consumed_at for grant in grants if grant.consumed_subject == row.canonical_subject
                )
        saved = await self.contacts.save(row)
        await self._audit(
            saved, "provisioned", {"identity_kind": value.identity.kind, "source": value.source}
        )
        return saved

    @transactional(datasource="primary", isolation=Isolation.SERIALIZABLE)
    async def renew(self, identifier, expected_revision: int, value: OperatorContactInput):
        await self._operator()
        await self.catalog._lock_tenant(value.tenant_id)
        row = await self.contacts.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if (
            row is None
            or row.tenant_id != value.tenant_id
            or row.identity_key != digest(value.identity.model_dump(mode="json"))
        ):
            raise recipient_unavailable()
        if row.revoked_at is not None or row.revision != expected_revision:
            raise ConflictException("Reload the current contact revision", code="CONTACT_REVISION_CHANGED")
        _, observed, expires = await self._observation(value)
        if observed < row.observed_at:
            raise ValueError("A contact renewal cannot precede its current observation")
        row.contact_ciphertext = self.cipher.seal(
            row.tenant_id, "operator_contact", value.model_dump(mode="json")
        )
        row.observed_at, row.expires_at, row.revision = observed, expires, row.revision + 1
        saved = await self.contacts.save(row)
        await self._audit(saved, "renewed")
        return saved

    @transactional(datasource="primary", isolation=Isolation.SERIALIZABLE)
    async def revoke(self, identifier, expected_revision: int):
        await self._operator()
        row = await self.contacts.find_by_id(identifier)
        if row is None:
            raise recipient_unavailable()
        await self.catalog._lock_tenant(row.tenant_id)
        row = await self.contacts.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row.revision != expected_revision:
            raise ConflictException("Reload the current contact revision", code="CONTACT_REVISION_CHANGED")
        if row.revoked_at is None:
            row.revoked_at, row.revision = await self._now(), row.revision + 1
            row = await self.contacts.save(row)
            await self._audit(row, "revoked")
        return row

    @primary_authority()
    async def _login_candidates(self, context):
        claims = context.attributes
        if (
            not context.is_authenticated
            or claims.get("sub") != context.user_id
            or claims.get("iss") != self.oidc.issuer
            or any(key in claims for key in ("koinon_token", "koinon_token_id", "koinon_mcp_grant"))
        ):
            return []
        audiences = claims.get("aud")
        if self.oidc.client_id not in ([audiences] if isinstance(audiences, str) else audiences or []):
            return []
        identifiers = [
            claims[key]
            for key in ("sub", "oid", "koinon_external_oid", "koinon_external_subject")
            if isinstance(claims.get(key), str)
        ]
        rows = await self.contacts._require_session().scalars(
            select(OperatorContactRecord)
            .where(
                OperatorContactRecord.revoked_at.is_(None),
                OperatorContactRecord.identity_json["issuer"].as_string() == self.oidc.issuer,
                OperatorContactRecord.identity_json["client_id"].as_string() == self.oidc.client_id,
                OperatorContactRecord.identity_json["external_subject"].as_string().in_(identifiers),
            )
            .limit(1001)
        )
        candidates = list(rows)
        if len(candidates) > 1000:
            return []
        result = []
        for row in candidates:
            identity = ContactIdentity.model_validate(row.identity_json)
            if not self._pins(identity) or identity.external_subject not in identifiers:
                continue
            try:
                verified = verified_identity(identity.policy(), claims)
            except Exception:
                continue
            if verified.external_subject == identity.external_subject:
                result.append((row.id, verified.subject))
        return result

    async def observe_login(self, context):
        tenants = set()
        for identifier, owner in await self._login_candidates(context):
            tenant = await self._bind(identifier, owner)
            if tenant:
                tenants.add(tenant)
        return tenants

    @transactional(datasource="primary", isolation=Isolation.SERIALIZABLE)
    async def _bind(self, identifier, owner):
        row = await self.contacts.find_by_id(identifier)
        if row is None:
            return None
        await self.catalog._lock_tenant(row.tenant_id)
        row = await self.contacts.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        now = await self._now()
        if not self._pins(ContactIdentity.model_validate(row.identity_json)):
            return None
        if row.revoked_at or row.expires_at <= now or not await self._admin(owner, row.tenant_id):
            return None
        if row.canonical_subject is not None:
            return row.tenant_id if self._binding_matches(row, owner) else None
        row.canonical_subject, row.bound_at = owner, now
        row.binding_ciphertext = self._seal_binding(row, owner)
        saved = await self.contacts.save(row)
        await self._audit(saved, "signed_identity_bound", actor="system:communications-identity")
        return row.tenant_id

    def _binding_matches(self, row, owner):
        if row.canonical_subject != owner or not row.binding_ciphertext or not row.bound_at:
            return False
        return self.cipher.open(row.tenant_id, "operator_contact_binding", row.binding_ciphertext) == {
            "contact_id": row.id,
            "identity_key": row.identity_key,
            "subject": owner,
            "configuration_sha256": self.configuration_sha256(),
        }

    async def _current(self, row, event):
        if (
            row is None
            or event.kind == "invitation"
            or not event.owner_subject
            or row.canonical_subject != event.owner_subject
        ):
            return None
        now = await self._now()
        identity = ContactIdentity.model_validate(row.identity_json)
        if (
            row.revoked_at
            or row.expires_at <= now
            or not self._pins(identity)
            or digest(row.identity_json) != row.identity_key
            or row.expires_at
            > row.observed_at + timedelta(days=self.settings.operator_contact_max_lifetime_days)
        ):
            return None
        if not self._binding_matches(row, event.owner_subject):
            return None
        if (event.event_json or {}).get("subtype") == "delivery_diagnostic" and not await self._admin(
            event.owner_subject, row.tenant_id
        ):
            return None
        value = OperatorContactInput.model_validate(
            self.cipher.open(row.tenant_id, "operator_contact", row.contact_ciphertext)
        )
        if (
            value.tenant_id != event.tenant_id
            or value.identity != identity
            or value.expires_at != row.expires_at
            or value.observed_at != row.observed_at
        ):
            return None
        return PreparedOperatorContact(
            row.id,
            row.tenant_id,
            event.owner_subject,
            row.revision,
            self.configuration_sha256(),
            DirectoryPerson(identity.external_subject, value.display_name, value.email, "verified_directory"),
        )

    @primary_authority()
    async def prepare(self, event):
        if event.kind == "invitation":
            return None
        requested = event.event_json.get("operator_contact_id")
        rows = await self.contacts.find_all(
            tenant_id=event.tenant_id,
            canonical_subject=event.owner_subject,
            **({"id": requested} if requested else {}),
        )
        if not rows:
            return None
        if len(rows) != 1:
            raise recipient_unavailable()
        prepared = await self._current(rows[0], event)
        if prepared is None:
            raise recipient_unavailable()
        return prepared

    async def validate(self, event, prepared):
        row = await self.contacts.find_by_id(prepared.id, lock=LockMode.PESSIMISTIC_WRITE)
        return await self._current(row, event) == prepared

    @primary_authority()
    async def status(self, identifier):
        row = await self.contacts.find_by_id(identifier)
        if row is None:
            raise recipient_unavailable()
        now = await self._now()
        state = (
            "revoked"
            if row.revoked_at is not None
            else "expired"
            if row.expires_at <= now
            else "pending_signed_login"
            if row.canonical_subject is None
            else "ineligible"
        )
        if state == "ineligible":
            observation = OutboxRecord(
                tenant_id=row.tenant_id, owner_subject=row.canonical_subject, kind="security"
            )
            if await self._current(row, observation) is not None:
                state = "eligible"
        policy = await self.policies.find_by_id(row.tenant_id)
        provider = self.readiness.observe(sender_id=policy.sender_id if policy else None).state
        expiry = (
            "expired"
            if row.expires_at <= now
            else "expiring"
            if row.expires_at <= now + timedelta(days=self.settings.operator_contact_expiry_warning_days)
            else "current"
        )
        administrative = bool(row.canonical_subject) and await self._admin(
            row.canonical_subject, row.tenant_id
        )
        return {
            "contact_id": row.id,
            "tenant_id": row.tenant_id,
            "revision": row.revision,
            "recipient_state": state,
            "provider_state": provider,
            "can_queue_diagnostic": state == "eligible" and provider == "ready" and administrative,
            "administrative_eligible": administrative,
            "expiry_state": expiry,
            "expires_at": row.expires_at.isoformat(),
        }

    @transactional(datasource="primary", isolation=Isolation.SERIALIZABLE)
    async def diagnostic(self, identifier, operation_id: str):
        await self._operator()
        operation = str(UUID(operation_id))
        row = await self.contacts.find_by_id(identifier)
        if row is None:
            raise recipient_unavailable()
        await self.catalog._lock_tenant(row.tenant_id)
        prior = await self.outbox.find_all(dedupe_key="operator-diagnostic:" + operation)
        if prior:
            if prior[0].event_json.get("operator_contact_id") != identifier:
                raise ConflictException(
                    "The diagnostic operation belongs to another contact", code="DIAGNOSTIC_OPERATION_CHANGED"
                )
            return {"delivery_id": prior[0].id, "status": prior[0].status}
        event = OutboxRecord(
            id=str(uuid4()),
            dedupe_key="operator-diagnostic:" + operation,
            tenant_id=row.tenant_id,
            owner_subject=row.canonical_subject,
            kind="security",
        )
        if await self._current(row, event) is None or not await self._admin(
            row.canonical_subject, row.tenant_id
        ):
            raise recipient_unavailable()
        now = await self._now()
        recent = await self.outbox._require_session().scalar(
            select(OutboxRecord.id)
            .where(
                OutboxRecord.tenant_id == row.tenant_id,
                OutboxRecord.owner_subject == row.canonical_subject,
                OutboxRecord.dedupe_key.like("operator-diagnostic:%"),
                OutboxRecord.created_at > now - timedelta(minutes=5),
            )
            .limit(1)
        )
        if recent:
            raise ConflictException(
                "Wait five minutes before another diagnostic", code="DIAGNOSTIC_THROTTLED"
            )
        policy = await self.policies.find_by_id(row.tenant_id)
        self.readiness.require_ready(sender_id=policy.sender_id if policy else None)
        tenant = await self.catalog.tenant_repository.find_by_id(row.tenant_id)
        event.event_json = {
            "subtype": "delivery_diagnostic",
            "operator_contact_id": row.id,
            "organization_name": tenant.name,
            "workspace_name": None,
            "actor_name": None,
        }
        event.status, event.created_at, event.next_attempt_at = "queued", now, now
        await self.outbox.save(event)
        await self._audit(row, "diagnostic_queued", {"delivery_id": event.id, "operation_id": operation})
        return {"delivery_id": event.id, "status": "queued"}
