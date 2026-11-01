# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Current organization authority gates policy and redacted delivery history separately."""

from datetime import UTC, datetime, timedelta
from typing import get_args

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.kernel import ConflictException, InvalidRequestException

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.communications.dtos import (
    CommunicationPolicy,
    CommunicationPolicyInput,
    DeliveryPage,
    DeliveryRecord,
    DeliveryStatus,
    DigestSchedule,
    EventKind,
)
from koinon.communications.entities import OutboxRecord
from koinon.communications.inbox import NotificationService
from koinon.communications.invitations import EmailInvitationService
from koinon.communications.locale_service import CommunicationLocales
from koinon.communications.readiness import EmailReadiness
from koinon.communications.repositories import CommunicationPolicyRepository, OutboxRepository
from koinon.communications.settings import CommunicationsSettings
from koinon.security.authority import primary_authority
from koinon.web.pagination import sql_page

PUBLIC_FAILURE_CODES = frozenset(
    {
        "EMAIL_DISABLED",
        "CHANNEL_PREFERENCE",
        "DELIVERY_IDENTITY_UNVERIFIED",
        "SEND_OUTCOME_UNKNOWN",
        "PROVIDER_REJECTED",
        "PROVIDER_SUPPRESSED",
        "PREPARATION_ATTEMPTS_EXHAUSTED",
        "DELIVERY_NO_LONGER_ELIGIBLE",
        "DELIVERY_IDENTITY_CHANGED",
        "SUMMARY_AUTHORIZATION_CHANGED",
        "PREPARATION_UNAVAILABLE",
        "DELIVERY_NOT_AUTHORIZED_OR_READY",
        "INVITATION_CLOSED",
        "INVITATION_CLOSED_IN_FLIGHT",
        "WELCOME_ALREADY_ADMITTED",
    }
)


@service(name="communications.administration")
class CommunicationsAdministration:
    def __init__(
        self,
        catalog: CatalogService,
        policies: CommunicationPolicyRepository,
        outbox: OutboxRepository,
        settings: CommunicationsSettings,
        readiness: EmailReadiness,
        inbox: NotificationService,
        locales: CommunicationLocales,
        invitations: EmailInvitationService | None = None,
    ):
        self.catalog, self.policies, self.outbox = catalog, policies, outbox
        self.settings, self.readiness, self.inbox, self.locales = settings, readiness, inbox, locales
        self.invitations = invitations

    @primary_authority()
    async def capabilities(self, actor, tenant_id):
        await self.catalog.authorize(actor, tenant_id, "members:write")
        row = await self.policies.find_by_id(tenant_id)
        result = self.readiness.observe(
            sender_id=row.sender_id if row else None, organization_locale=row.default_locale if row else None
        )
        locale, origin = await self.locales.resolve(owner=actor, tenant_id=tenant_id)
        return result.model_copy(update={"effective_locale": locale, "locale_origin": origin})

    @primary_authority()
    async def policy(self, actor, tenant_id):
        await self.catalog.authorize(actor, tenant_id, "members:write")
        row = await self.policies.find_by_id(tenant_id)
        return CommunicationPolicy(
            revision=row.revision if row else 0,
            sender_id=row.sender_id if row else None,
            rules=self.inbox._rules(row.rules_json if row else [], row.sender_id if row else None),
            digest_enabled=row.digest_enabled if row else False,
            can_update=True,
            allowed_digests=row.allowed_digests_json if row else ["off"],
            default_digest=row.default_digest if row else "off",
            default_schedule=DigestSchedule.model_validate(row.default_schedule_json if row else {}),
            default_locale=row.default_locale if row else None,
            admin_summaries=row.admin_summaries_json if row else [],
        )

    @transactional
    async def update_policy(self, actor, tenant_id, body: CommunicationPolicyInput):
        body = CommunicationPolicyInput.model_validate(body)
        await self.catalog._lock_tenant(tenant_id)
        current = await self.policy(actor, tenant_id)
        if body.sender_id is not None and body.sender_id not in {
            item.id for item in self.settings.sender_options()
        }:
            raise InvalidRequestException(
                "Choose an operator-verified sender", code="INVALID_COMMUNICATION_SENDER"
            )
        if (
            len({item.kind for item in body.rules}) != len(body.rules)
            or len(set(body.allowed_digests)) != len(body.allowed_digests)
            or "off" not in body.allowed_digests
            or body.default_digest not in body.allowed_digests
            or not body.digest_enabled
            and set(body.allowed_digests) != {"off"}
        ):
            raise InvalidRequestException(
                "Choose coherent communication policies", code="INVALID_COMMUNICATION_POLICY"
            )
        if len({item.cadence for item in body.admin_summaries}) != len(body.admin_summaries):
            raise InvalidRequestException(
                "Choose each administrative cadence at most once", code="INVALID_COMMUNICATION_POLICY"
            )
        required = {item.kind: item for item in current.rules if item.required}
        for item in body.rules:
            if item.kind in required and (not item.inbox or required[item.kind].email and not item.email):
                raise InvalidRequestException(
                    "Required access and security notices cannot be disabled", code="REQUIRED_NOTIFICATION"
                )
        values = dict(
            sender_id=body.sender_id,
            rules_json=[item.model_dump() for item in body.rules],
            digest_enabled=body.digest_enabled,
            allowed_digests_json=body.allowed_digests,
            default_digest=body.default_digest,
            default_schedule_json=body.default_schedule.model_dump(),
            default_locale=body.default_locale,
            admin_summaries_json=[item.model_dump() for item in body.admin_summaries],
        )
        if not await self.policies.compare_and_swap(tenant_id, body.expected_revision, values):
            raise ConflictException(
                "Communication policy changed; reload and try again", code="COMMUNICATION_POLICY_CHANGED"
            )
        await self.catalog._audit(
            actor,
            tenant_id,
            "communications.policy.updated",
            tenant_id,
            dict(revision=body.expected_revision + 1),
        )
        return await self.policy(actor, tenant_id)

    async def _delivery(self, row, locale):
        can_retry = False
        if (
            self.invitations is not None
            and row.invitation_id
            and row.status in {"failed", "suppressed"}
            and row.failure_code in PUBLIC_FAILURE_CODES
        ):
            invitation = await self.invitations.invitations.find_by_id(row.invitation_id)
            if invitation is not None and invitation.delivery_id == row.id:
                can_retry = "resend" in (await self.invitations._view(invitation)).allowed_actions
        return DeliveryRecord(
            id=row.id,
            kind=row.kind,
            invitation_id=row.invitation_id,
            membership_id=row.membership_id,
            recipient_display="Cuenta" if locale.startswith("es") else "Account",
            scope_name=("Espacio de trabajo" if locale.startswith("es") else "Workspace")
            if row.workspace_id
            else ("Organización" if locale.startswith("es") else "Organization"),
            status="queued" if row.status == "preparing" else row.status,
            created_at=row.created_at,
            last_attempt_at=row.last_attempt_at,
            next_attempt_at=row.next_attempt_at if row.status in {"queued", "deferred"} else None,
            attempt_count=row.attempt_count,
            failure_code=row.failure_code if row.failure_code in PUBLIC_FAILURE_CODES else None,
            safe_explanation=None,
            can_retry=can_retry,
        )

    @staticmethod
    def _date(value):
        if value is None:
            return None
        try:
            result = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
            if not isinstance(result, datetime) or result.utcoffset() is None:
                raise ValueError()
            return result.astimezone(UTC)
        except (ValueError, TypeError):
            raise InvalidRequestException(
                "Choose an aware delivery date filter", code="INVALID_DELIVERY_FILTER"
            ) from None

    @primary_authority()
    async def deliveries(
        self,
        actor,
        tenant_id,
        *,
        workspace_id=None,
        status=None,
        kind=None,
        channel="email",
        created_from=None,
        created_to=None,
        page=1,
        page_size=25,
    ):
        await self.catalog.authorize(actor, tenant_id, "members:write", workspace_id)
        if (
            channel != "email"
            or status is not None
            and status not in get_args(DeliveryStatus)
            or kind is not None
            and kind not in get_args(EventKind)
        ):
            raise InvalidRequestException("Choose supported delivery filters", code="INVALID_DELIVERY_FILTER")
        start, end = self._date(created_from), self._date(created_to)
        if start is not None and end is not None and not timedelta(0) < end - start <= timedelta(days=366):
            raise InvalidRequestException(
                "Choose a delivery window of at most 366 days", code="INVALID_DELIVERY_FILTER"
            )
        predicates = [OutboxRecord.tenant_id == tenant_id]
        if workspace_id is not None:
            predicates.append(OutboxRecord.workspace_id == workspace_id)
        if status is not None:
            predicates.append(
                OutboxRecord.status.in_(("queued", "preparing"))
                if status == "queued"
                else OutboxRecord.status == status
            )
        if kind is not None:
            predicates.append(OutboxRecord.kind == kind)
        if start is not None:
            predicates.append(OutboxRecord.created_at >= start)
        if end is not None:
            predicates.append(OutboxRecord.created_at < end)
        values = await sql_page(
            OutboxRecord, predicates, page=page, page_size=page_size, sorts=("created_at",)
        )
        locale, _ = await self.locales.resolve(owner=actor, tenant_id=tenant_id)
        return DeliveryPage(
            **{**values, "items": [await self._delivery(row, locale) for row in values["items"]]}
        )

    @primary_authority()
    async def delivery(self, actor, tenant_id, identifier):
        row = await self.outbox.find_by_id(identifier)
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("Delivery record is unavailable", code="DELIVERY_UNAVAILABLE")
        await self.catalog.authorize(actor, tenant_id, "members:write", row.workspace_id)
        locale, _ = await self.locales.resolve(owner=actor, tenant_id=tenant_id)
        return await self._delivery(row, locale)

    async def retry(self, actor, tenant_id, identifier):
        record = await self.delivery(actor, tenant_id, identifier)
        if not record.can_retry or self.invitations is None or record.invitation_id is None:
            raise InvalidRequestException(
                "This delivery cannot be safely resubmitted", code="DELIVERY_RETRY_UNAVAILABLE"
            )
        current = await self.invitations.resend(actor, tenant_id, record.invitation_id)
        return await self.delivery(actor, tenant_id, current.delivery.id)
