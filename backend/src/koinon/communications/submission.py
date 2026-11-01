# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One encrypted MIME payload; fresh directory identity and current authority fence submission."""

import base64
import json
from datetime import datetime
from hashlib import sha256

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ServiceUnavailableException
from pyfly.notifications import Attachment, EmailMessage

from koinon.activity.dtos import ActivityWindow
from koinon.activity.ports import ActivitySummaryReader
from koinon.communications.content import CommunicationContent
from koinon.communications.crypto import CommunicationsCipher
from koinon.communications.delivery import EmailDispatcher
from koinon.communications.digest import DigestScheduler
from koinon.communications.invitations import EmailInvitationService
from koinon.communications.mappers import invitation_status
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.readiness import EmailReadiness
from koinon.communications.recipients import RecipientService, recipient_unavailable
from koinon.communications.repositories import (
    CommunicationPolicyRepository,
    EmailInvitationRepository,
    OutboxRepository,
    RecipientIdentityRepository,
)
from koinon.communications.settings import CommunicationsSettings, InstallationLinks
from koinon.communications.templates import EmailRenderer
from koinon.security.authority import primary_authority


def _encoded(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


@service(name="communications.submission")
class EmailSubmission:
    def __init__(
        self,
        state: CommunicationOutbox,
        outbox: OutboxRepository,
        invitations: EmailInvitationRepository,
        invitation_service: EmailInvitationService,
        recipients: RecipientService,
        content: CommunicationContent,
        renderer: EmailRenderer,
        cipher: CommunicationsCipher,
        readiness: EmailReadiness,
        policies: CommunicationPolicyRepository,
        settings: CommunicationsSettings,
        links: InstallationLinks,
        dispatcher: EmailDispatcher,
        identities: RecipientIdentityRepository,
        digests: DigestScheduler,
        summaries: ActivitySummaryReader | None = None,
    ):
        self.state, self.outbox, self.invitations, self.invitation_service = (
            state,
            outbox,
            invitations,
            invitation_service,
        )
        self.recipients, self.content, self.renderer, self.cipher = recipients, content, renderer, cipher
        self.readiness, self.policies, self.settings, self.links, self.dispatcher = (
            readiness,
            policies,
            settings,
            links,
            dispatcher,
        )
        self.identities, self.digests, self.summaries = identities, digests, summaries

    async def _notice_allowed(self, event):
        if event.kind in {"security", "access_removed"}:
            return True
        if event.kind == "digest":
            return await self.digests.current(event)
        members = await self.invitation_service.catalog.memberships(event.owner_subject)
        if event.kind == "welcome":
            return any(
                row.tenant_id == event.tenant_id and row.workspace_id is None and row.role == "admin"
                for row in members
            )
        return any(row.id == event.membership_id for row in members)

    @primary_authority()
    async def _target(self, ticket):
        event = await self.outbox.find_by_id(ticket.id)
        if event is None:
            return None
        if event.kind == "invitation":
            row = await self.invitations.find_by_id(event.invitation_id)
            if (
                row is None
                or row.delivery_id != ticket.id
                or invitation_status(row, await self.outbox.clock()) != "pending"
            ):
                return None
            await self.invitation_service._inviter(row)
            return (
                event,
                row,
                await self.recipients.snapshot(row.tenant_id, row.provider_id),
                row.external_subject,
            )
        if not await self._notice_allowed(event):
            return None
        bindings = await self.identities.find_all(tenant_id=event.tenant_id, subject=event.owner_subject)
        if len(bindings) != 1:
            raise recipient_unavailable()
        binding = bindings[0]
        provider = await self.recipients.snapshot(event.tenant_id, binding.provider_id)
        if provider.revision != binding.provider_revision:
            raise recipient_unavailable()
        return event, None, provider, binding.external_subject

    @primary_authority()
    async def _sender(self, tenant_id):
        policy = await self.policies.find_by_id(tenant_id)
        return self.readiness.require_ready(sender_id=policy.sender_id if policy else None)

    async def _summary(self, event):
        if self.summaries is None:
            raise ServiceUnavailableException(
                "Activity summaries are not configured", code="ACTIVITY_SUMMARIES_UNAVAILABLE"
            )
        values = event.event_json
        window = ActivityWindow(
            start_at=datetime.fromisoformat(values["window_start"]),
            end_at=datetime.fromisoformat(values["window_end"]),
            time_zone=values["time_zone"],
        )
        method = (
            self.summaries.administrative
            if values["audience"] == "organization_administrators"
            else self.summaries.personal
        )
        return await method(event.owner_subject, event.tenant_id, window)

    @transactional
    async def _begin(self, ticket, prepared, expected_owner):
        await self.invitation_service.catalog._lock_tenant(prepared.provider.tenant_id)
        event = await self.outbox.find_by_id(ticket.id, lock=LockMode.PESSIMISTIC_WRITE)
        if event is None or event.owner_subject != expected_owner:
            return False
        await self.recipients.ensure_current(prepared.provider)
        self.invitation_service._fresh(prepared)
        if event.kind == "invitation":
            row = await self.invitations.find_by_id(event.invitation_id, lock=LockMode.PESSIMISTIC_WRITE)
            if (
                row is None
                or row.delivery_id != ticket.id
                or row.provider_revision != prepared.provider.revision
                or invitation_status(row, await self.outbox.clock()) != "pending"
            ):
                return False
            await self.invitation_service._inviter(row)
        else:
            if not await self._notice_allowed(event):
                return False
            bindings = await self.identities.find_all(
                tenant_id=event.tenant_id,
                subject=event.owner_subject,
                provider_id=prepared.provider.id,
                external_subject=prepared.person.external_subject,
            )
            if len(bindings) != 1 or bindings[0].provider_revision != prepared.provider.revision:
                return False
        policy = await self.policies.find_by_id(event.tenant_id)
        self.readiness.require_ready(sender_id=policy.sender_id if policy else None)
        return await self.state.begin_send(ticket)

    async def execute(self, ticket):
        try:
            target = await self._target(ticket)
            if target is None:
                await self.state.stop_preparation(
                    ticket, "cancelled", failure_code="DELIVERY_NO_LONGER_ELIGIBLE"
                )
                return
            event, invitation, provider, external = target
            prepared = await self.recipients.observe(provider, external)
            sender = await self._sender(event.tenant_id)
            summary = await self._summary(event) if event.kind == "digest" else None
            summary_hash = sha256(summary.model_dump_json().encode()).hexdigest() if summary else None
            if ticket.payload_ciphertext:
                payload = self.cipher.open(event.tenant_id, "delivery", ticket.payload_ciphertext)
                if sha256(_encoded(payload)).hexdigest() != ticket.payload_hash:
                    raise ValueError("Stored payload hash mismatch")
            else:
                preview = (
                    await self.content.invitation(invitation)
                    if invitation
                    else await self.content.digest(event, prepared.person, summary)
                    if summary
                    else await self.content.notice(event, prepared.person)
                )
                action = (
                    self.links.invitation_url(invitation.id, client_path=self.settings.acceptance_client_path)
                    if invitation
                    else self.links.public_url
                    + (
                        "/auth/notifications/preferences"
                        if summary
                        else "/auth/setup"
                        if event.kind == "welcome"
                        else "/auth/notifications"
                    )
                )
                rendered = await self.renderer.render(
                    preview,
                    action_url=action,
                    preferences_url=self.links.public_url + "/auth/notifications/preferences"
                    if summary
                    else None,
                    locale=preview.effective_locale,
                )
                payload = dict(
                    id=ticket.id,
                    to=prepared.person.email,
                    sender=sender.sender_address,
                    subject=preview.subject,
                    body_text=rendered.text,
                    body_html=rendered.html,
                    summary_sha256=summary_hash,
                    attachments=[
                        dict(
                            content_id=image.content_id,
                            content_type=image.content_type,
                            data=base64.b64encode(image.data).decode(),
                        )
                        for image in rendered.images
                    ],
                )
                if not await self.state.write_payload(
                    ticket,
                    self.cipher.seal(event.tenant_id, "delivery", payload),
                    sha256(_encoded(payload)).hexdigest(),
                ):
                    return
            if (
                payload["to"] != prepared.person.email
                or payload["sender"] != sender.sender_address
                or payload["id"] != ticket.id
                or payload.get("summary_sha256") != summary_hash
            ):
                await self.state.stop_preparation(
                    ticket, "cancelled", failure_code="DELIVERY_IDENTITY_CHANGED"
                )
                return
            if summary:
                current = await self._summary(event)
                if sha256(current.model_dump_json().encode()).hexdigest() != summary_hash:
                    await self.state.stop_preparation(
                        ticket, "cancelled", failure_code="SUMMARY_AUTHORIZATION_CHANGED"
                    )
                    return
            message = EmailMessage(
                id=payload["id"],
                to=[payload["to"]],
                sender=payload["sender"],
                subject=payload["subject"],
                body_text=payload["body_text"],
                body_html=payload["body_html"],
                attachments=[
                    Attachment(
                        filename="brand-logo.png",
                        content_type=image["content_type"],
                        data=base64.b64decode(image["data"], validate=True),
                        content_id=image["content_id"],
                        inline=True,
                    )
                    for image in payload["attachments"]
                ],
            )
            if await self._begin(ticket, prepared, event.owner_subject):
                await self.dispatcher.send(ticket, message)
            else:
                await self.state.stop_preparation(
                    ticket, "cancelled", failure_code="DELIVERY_NO_LONGER_ELIGIBLE"
                )
        except ServiceUnavailableException as error:
            disabled = error.code == "COMMUNICATIONS_NOT_READY"
            await self.state.stop_preparation(
                ticket,
                "suppressed" if disabled else "deferred",
                failure_code="EMAIL_DISABLED" if disabled else "PREPARATION_UNAVAILABLE",
            )
        except Exception:
            await self.state.stop_preparation(
                ticket, "suppressed", failure_code="DELIVERY_NOT_AUTHORIZED_OR_READY"
            )
