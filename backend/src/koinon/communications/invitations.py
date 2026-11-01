# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Recipient-bound grant intentions; fresh identity and transaction-fenced exact acceptance."""

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import and_

from koinon.catalog.service import CatalogService
from koinon.communications.crypto import CommunicationsCipher
from koinon.communications.dtos import EmailInvitationInput, EmailInvitationPage
from koinon.communications.entities import EmailInvitationRecord, OutboxRecord, RecipientIdentityRecord
from koinon.communications.mappers import invitation_dto, invitation_review, invitation_status
from koinon.communications.readiness import EmailReadiness
from koinon.communications.recipients import RecipientService, recipient_unavailable
from koinon.communications.repositories import (
    CommunicationPolicyRepository,
    EmailInvitationRepository,
    OutboxRepository,
    RecipientIdentityRepository,
)
from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.security.authority import primary_authority
from koinon.web.pagination import sql_page


@service(name="communications.email_invitations")
class EmailInvitationService:
    def __init__(
        self,
        invitations: EmailInvitationRepository,
        recipients: RecipientService,
        catalog: CatalogService,
        outbox: OutboxRepository,
        identities: RecipientIdentityRepository,
        cipher: CommunicationsCipher,
        settings: CommunicationsSettings,
        links: InstallationLinks,
        readiness: EmailReadiness,
        policies: CommunicationPolicyRepository,
    ):
        self.invitations, self.recipients, self.catalog, self.outbox = (
            invitations,
            recipients,
            catalog,
            outbox,
        )
        self.identities, self.cipher, self.settings, self.links = identities, cipher, settings, links
        self.readiness, self.policies = readiness, policies

    @primary_authority()
    async def _enabled(self, tenant_id):
        if not self.settings.enabled or not self.links.public_url or not self.settings.sender_options():
            raise ServiceUnavailableException(
                "Configure communications, a canonical public origin and a verified sender",
                code="COMMUNICATIONS_NOT_READY",
            )
        policy = await self.policies.find_by_id(tenant_id)
        self.readiness.require_ready(sender_id=policy.sender_id if policy else None)

    @staticmethod
    def _outside_transaction():
        if current_unit_of_work("primary") is not None:
            raise RuntimeError("Directory verification requires no ambient primary transaction")

    @staticmethod
    def _request(actor, body, key):
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= 128
            or any(ord(c) < 33 or ord(c) > 126 for c in key)
        ):
            raise InvalidRequestException(
                "Provide a bounded Idempotency-Key", code="INVITATION_IDEMPOTENCY_REQUIRED"
            )
        request_key = sha256(json.dumps([actor, key], separators=(",", ":")).encode()).hexdigest()
        request_hash = sha256(body.model_dump_json().encode()).hexdigest()
        return request_key, request_hash

    async def _view(self, row):
        recipient = self.cipher.open(row.tenant_id, "delivery", row.recipient_ciphertext)
        delivery = await self.outbox.find_by_id(row.delivery_id)
        value = invitation_dto(row, recipient, delivery, await self.outbox.clock(), self.settings)
        reason = await self._authority_reason(row)
        if reason:
            return value.model_copy(
                update={
                    "allowed_actions": [action for action in value.allowed_actions if action != "resend"],
                    "action_reasons": {"resend": reason},
                }
            )
        reasons = (
            {}
            if "resend" in value.allowed_actions
            else {
                "resend": "delivery_outcome_unknown"
                if delivery.status == "unknown"
                else "closed"
                if value.status != "pending"
                else "send_limit"
                if row.send_count >= self.settings.max_invitation_sends
                else "cooldown"
            }
        )
        return value.model_copy(update={"action_reasons": reasons})

    @primary_authority()
    async def _existing(self, actor, tenant_id, request_key, request_hash):
        rows = await self.invitations.find_all(tenant_id=tenant_id, request_key=request_key)
        if not rows:
            return None
        row = rows[0]
        await self.catalog.authorize(actor, tenant_id, "members:write", row.workspace_id)
        if row.request_hash != request_hash or row.created_by != actor:
            raise ConflictException(
                "This invitation request key was already used", code="INVITATION_REQUEST_CONFLICT"
            )
        return await self._view(row)

    async def create(self, actor, tenant_id, body: EmailInvitationInput, idempotency_key):
        self._outside_transaction()
        body = EmailInvitationInput.model_validate(body)
        key, digest = self._request(actor, body, idempotency_key)
        previous = await self._existing(actor, tenant_id, key, digest)
        if previous is not None:
            return previous
        prepared = await self.recipients.resolve(actor, tenant_id, body)
        await self._enabled(tenant_id)
        return await self._create(actor, tenant_id, body, key, digest, prepared)

    async def _workspace(self, tenant_id, workspace_id):
        await self.catalog._validate_workspace(tenant_id, workspace_id)
        if workspace_id is None:
            return None
        row = await self.catalog.catalog_repository.find_by_id(workspace_id)
        if row.kind != "workspace" or row.status == "archived":
            raise recipient_unavailable()
        return row

    @transactional
    async def _create(self, actor, tenant_id, body, request_key, request_hash, prepared):
        await self.catalog._lock_tenant(tenant_id)
        await self.catalog.authorize(actor, tenant_id, "members:write", body.workspace_id)
        await self._enabled(tenant_id)
        previous = await self._existing(actor, tenant_id, request_key, request_hash)
        if previous is not None:
            return previous
        await self.recipients.ensure_current(prepared.provider, actor=actor, workspace_id=body.workspace_id)
        self._fresh(prepared)
        if await self.recipients.exact_membership(
            prepared.provider, prepared.person.external_subject, body.workspace_id
        ):
            raise ConflictException(
                "This person already has a role assignment in this scope", code="MEMBERSHIP_EXISTS"
            )
        workspace = await self._workspace(tenant_id, body.workspace_id)
        tenant = await self.catalog.tenant_repository.find_by_id(tenant_id)
        now = await self.outbox.clock()
        identifier, delivery_id = str(uuid4()), str(uuid4())
        self.links.invitation_url(identifier, client_path=self.settings.acceptance_client_path)
        context = SecurityContextHolder.get_context()
        origin_token = context.attributes.get("koinon_token_id") if context else None
        row = EmailInvitationRecord(
            id=identifier,
            tenant_id=tenant_id,
            workspace_id=body.workspace_id,
            role=body.role,
            provider_id=prepared.provider.id,
            provider_revision=prepared.provider.revision,
            external_subject=prepared.person.external_subject,
            recipient_ciphertext=self.cipher.seal(
                tenant_id,
                "delivery",
                dict(
                    display_name=prepared.person.display_name,
                    email=prepared.person.email,
                    message=body.message,
                    organization_name=tenant.name,
                    workspace_name=workspace.name if workspace else None,
                    provider_label=prepared.provider.name,
                ),
            ),
            created_by=actor,
            origin_token_id=origin_token,
            request_key=request_key,
            request_hash=request_hash,
            created_at=now,
            expires_at=now + timedelta(hours=body.expires_in_hours),
            send_count=1,
            last_queued_at=now,
            delivery_id=delivery_id,
        )
        await self.invitations.save(row)
        await self._enqueue(row, delivery_id, now)
        await self.catalog._audit(
            actor,
            tenant_id,
            "email_invitation.created",
            row.id,
            dict(role=row.role, workspace_id=row.workspace_id),
        )
        return await self._view(row)

    @staticmethod
    def _fresh(prepared):
        if not 0 <= (datetime.now(UTC) - prepared.observed_at).total_seconds() <= 30:
            raise recipient_unavailable()

    async def _enqueue(self, row, identifier, now):
        await self.outbox.save(
            OutboxRecord(
                id=identifier,
                dedupe_key=f"invitation:{row.id}:{row.send_count}",
                tenant_id=row.tenant_id,
                workspace_id=row.workspace_id,
                kind="invitation",
                invitation_id=row.id,
                event_json={},
                status="queued",
                created_at=now,
                next_attempt_at=now,
            )
        )

    @primary_authority()
    async def _recipient_snapshot(self, actor, identifier, claims):
        try:
            identifier = str(UUID(identifier))
        except (ValueError, TypeError):
            raise recipient_unavailable() from None
        row = await self.invitations.find_by_id(identifier)
        if row is None:
            raise recipient_unavailable()
        provider = await self.recipients.snapshot(row.tenant_id, row.provider_id)
        self.recipients.require_identity(actor, claims, provider, row.external_subject)
        if provider.revision != row.provider_revision:
            raise recipient_unavailable()
        return row, provider

    async def _prepare_recipient(self, actor, identifier, claims):
        self._outside_transaction()
        row, provider = await self._recipient_snapshot(actor, identifier, claims)
        prepared = await self.recipients.observe(provider, row.external_subject)
        return row, prepared

    async def _authority_reason(self, row):
        context = self._inviter_context(row)
        context.attributes.pop("koinon_token_id", None)
        with SecurityContextHolder.using(context):
            members = await self.catalog.memberships(row.created_by)
        token = None
        if row.origin_token_id:
            if self.catalog.restriction is None:
                return "origin_scope_changed"
            token = await self.catalog.restriction.tokens.find_by_id(row.origin_token_id)
            if token is None or token.revoked_at is not None:
                return "origin_token_revoked"
            if token.expires_at <= await self.outbox.clock():
                return "origin_token_expired"
            if token.subject != row.created_by or token.purpose != "personal":
                return "origin_scope_changed"
        if "members:write" not in self.catalog._resolved_permissions(
            members, row.tenant_id, row.workspace_id, token
        ):
            return "inviter_authority_lost" if token is None else "origin_scope_changed"
        provider = await self.recipients.providers.find_by_id(row.provider_id)
        if provider is None or provider.status != "active" or provider.revision != row.provider_revision:
            return "recipient_connection_changed"
        return None

    async def _inviter(self, row):
        with SecurityContextHolder.using(self._inviter_context(row)):
            await self.catalog.authorize(row.created_by, row.tenant_id, "members:write", row.workspace_id)
        await self._workspace(row.tenant_id, row.workspace_id)

    def _inviter_context(self, row):
        issuer, separator, subject = row.created_by.partition("|")
        if not separator or not subject or row.origin_token_id and self.catalog.restriction is None:
            raise recipient_unavailable()
        attributes = {"iss": issuer, "sub": subject}
        if row.origin_token_id:
            attributes["koinon_token_id"] = row.origin_token_id
        return SecurityContext(user_id=subject, attributes=attributes)

    async def review(self, actor, identifier, claims):
        _, prepared = await self._prepare_recipient(actor, identifier, claims)
        return await self._review(actor, identifier, claims, prepared)

    @primary_authority()
    async def _review(self, actor, identifier, claims, prepared):
        row, _ = await self._recipient_snapshot(actor, identifier, claims)
        await self.recipients.ensure_current(prepared.provider)
        self._fresh(prepared)
        now = await self.outbox.clock()
        reason = await self._authority_reason(row) if invitation_status(row, now) == "pending" else "closed"
        value = invitation_review(
            row,
            self.cipher.open(row.tenant_id, "delivery", row.recipient_ciphertext),
            now,
            can_accept=reason is None,
        )
        return value.model_copy(update={"action_reasons": {"accept": reason} if reason else {}})

    async def accept(self, actor, identifier, claims):
        _, prepared = await self._prepare_recipient(actor, identifier, claims)
        return await self._decision(actor, identifier, claims, prepared, accept=True)

    async def decline(self, actor, identifier, claims):
        _, prepared = await self._prepare_recipient(actor, identifier, claims)
        return await self._decision(actor, identifier, claims, prepared, accept=False)

    @transactional
    async def _decision(self, actor, identifier, claims, prepared, *, accept):
        await self.catalog._lock_tenant(prepared.provider.tenant_id)
        row = await self.invitations.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != prepared.provider.tenant_id:
            raise recipient_unavailable()
        await self.recipients.ensure_current(prepared.provider)
        self.recipients.require_identity(actor, claims, prepared.provider, row.external_subject)
        self._fresh(prepared)
        now = await self.outbox.clock()
        if invitation_status(row, now) != "pending":
            raise ConflictException("This invitation is already closed", code="EMAIL_INVITATION_TERMINAL")
        if row.provider_revision != prepared.provider.revision:
            raise recipient_unavailable()
        if accept:
            await self._inviter(row)
            await self._bind(actor, row, now)
            with SecurityContextHolder.using(self._inviter_context(row)):
                member = await self.catalog.create_member(
                    row.created_by, row.tenant_id, subject=actor, role=row.role, workspace_id=row.workspace_id
                )
            row.accepted_at, row.accepted_by, row.membership_id = now, actor, member.id
        else:
            row.declined_at = now
        await self.invitations.save(row)
        await self._cancel_delivery(row, now)
        await self.catalog._audit(
            actor,
            row.tenant_id,
            "email_invitation.accepted" if accept else "email_invitation.declined",
            row.id,
        )
        if accept:
            return member
        return invitation_review(
            row, self.cipher.open(row.tenant_id, "delivery", row.recipient_ciphertext), now, can_accept=False
        )

    async def _bind(self, actor, invitation, now):
        rows = await self.identities.find_all(
            tenant_id=invitation.tenant_id,
            provider_id=invitation.provider_id,
            external_subject=invitation.external_subject,
        )
        by_subject = await self.identities.find_all(
            tenant_id=invitation.tenant_id, provider_id=invitation.provider_id, subject=actor
        )
        if (
            rows
            and rows[0].subject != actor
            or by_subject
            and by_subject[0].external_subject != invitation.external_subject
        ):
            raise recipient_unavailable()
        row = (
            rows[0]
            if rows
            else RecipientIdentityRecord(
                id=str(uuid4()),
                tenant_id=invitation.tenant_id,
                provider_id=invitation.provider_id,
                external_subject=invitation.external_subject,
                subject=actor,
            )
        )
        row.provider_revision, row.verified_at = invitation.provider_revision, now
        await self.identities.save(row)

    async def _cancel_delivery(self, row, now):
        delivery = await self.outbox.find_by_id(row.delivery_id, lock=LockMode.PESSIMISTIC_WRITE)
        if delivery.status in {"queued", "deferred", "preparing", "sending"}:
            delivery.status = "unknown" if delivery.status == "sending" else "cancelled"
            delivery.generation += 1
            delivery.lease_owner = delivery.lease_until = None
            delivery.completed_at = now
            delivery.failure_code = (
                "INVITATION_CLOSED_IN_FLIGHT" if delivery.status == "unknown" else "INVITATION_CLOSED"
            )
            await self.outbox.save(delivery)

    @transactional
    async def revoke(self, actor, tenant_id, identifier):
        await self.catalog._lock_tenant(tenant_id)
        row = await self.invitations.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != tenant_id:
            raise recipient_unavailable()
        await self.catalog.authorize(actor, tenant_id, "members:write", row.workspace_id)
        if row.accepted_at or row.declined_at:
            raise ConflictException("This invitation is already closed", code="EMAIL_INVITATION_TERMINAL")
        if row.revoked_at is None:
            now = await self.outbox.clock()
            row.revoked_at = now
            await self.invitations.save(row)
            await self._cancel_delivery(row, now)
            await self.catalog._audit(actor, tenant_id, "email_invitation.revoked", row.id)

    @primary_authority()
    async def _resend_target(self, actor, tenant_id, identifier):
        row = await self.invitations.find_by_id(identifier)
        if row is None or row.tenant_id != tenant_id:
            raise recipient_unavailable()
        await self.catalog.authorize(actor, tenant_id, "members:write", row.workspace_id)
        await self._inviter(row)
        return row, await self.recipients.snapshot(tenant_id, row.provider_id)

    async def resend(self, actor, tenant_id, identifier):
        self._outside_transaction()
        row, provider = await self._resend_target(actor, tenant_id, identifier)
        await self._enabled(tenant_id)
        prepared = await self.recipients.observe(provider, row.external_subject)
        return await self._resend(actor, tenant_id, identifier, prepared)

    @transactional
    async def _resend(self, actor, tenant_id, identifier, prepared):
        await self.catalog._lock_tenant(tenant_id)
        row = await self.invitations.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if row is None or row.tenant_id != tenant_id:
            raise recipient_unavailable()
        await self.catalog.authorize(actor, tenant_id, "members:write", row.workspace_id)
        await self._inviter(row)
        await self.recipients.ensure_current(prepared.provider)
        self._fresh(prepared)
        if row.provider_revision != prepared.provider.revision:
            raise recipient_unavailable()
        current = await self._view(row)
        if "resend" not in current.allowed_actions:
            raise ConflictException(
                "This invitation cannot be resent yet", code="INVITATION_RESEND_UNAVAILABLE"
            )
        now = await self.outbox.clock()
        await self._cancel_delivery(row, now)
        recipient = self.cipher.open(tenant_id, "delivery", row.recipient_ciphertext)
        recipient.update(email=prepared.person.email, display_name=prepared.person.display_name)
        row.recipient_ciphertext = self.cipher.seal(tenant_id, "delivery", recipient)
        row.send_count += 1
        row.last_queued_at, row.delivery_id = now, str(uuid4())
        await self.invitations.save(row)
        await self._enqueue(row, row.delivery_id, now)
        await self.catalog._audit(actor, tenant_id, "email_invitation.resent", row.id)
        return await self._view(row)

    @primary_authority()
    async def page(self, actor, tenant_id, *, workspace_id=None, status="pending", page=1, page_size=25):
        await self.catalog.authorize(actor, tenant_id, "members:write", workspace_id)
        now = await self.outbox.clock()
        open_record = and_(
            EmailInvitationRecord.accepted_at.is_(None),
            EmailInvitationRecord.declined_at.is_(None),
            EmailInvitationRecord.revoked_at.is_(None),
        )
        statuses = {
            "pending": and_(open_record, EmailInvitationRecord.expires_at > now),
            "expired": and_(open_record, EmailInvitationRecord.expires_at <= now),
            "accepted": EmailInvitationRecord.accepted_at.is_not(None),
            "declined": EmailInvitationRecord.declined_at.is_not(None),
            "revoked": EmailInvitationRecord.revoked_at.is_not(None),
        }
        if status not in {*statuses, "all"}:
            raise InvalidRequestException(
                "Choose a supported invitation status", code="INVALID_INVITATION_FILTER"
            )
        predicates = [EmailInvitationRecord.tenant_id == tenant_id]
        if workspace_id is not None:
            predicates.append(EmailInvitationRecord.workspace_id == workspace_id)
        if status != "all":
            predicates.append(statuses[status])
        result = await sql_page(
            EmailInvitationRecord, predicates, page=page, page_size=page_size, sorts=("created_at",)
        )
        return EmailInvitationPage(**{**result, "items": [await self._view(row) for row in result["items"]]})
