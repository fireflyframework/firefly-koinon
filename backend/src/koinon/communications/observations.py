# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit operation lookups never submit mail or infer recipient delivery."""

import asyncio
import re
from datetime import UTC, timedelta
from hashlib import sha256
from urllib.parse import urlsplit
from uuid import uuid4

from pyfly.container import Container, service
from pyfly.container.exceptions import NoSuchBeanError
from pyfly.core import Config
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.data.transaction import current_unit_of_work
from pyfly.kernel import ConflictException, InvalidRequestException, ServiceUnavailableException
from pyfly.notifications import EmailStatus
from pyfly.notifications.capabilities import email_capabilities
from pyfly.notifications.ports import EmailOperationProvider, EmailProvider
from pyfly.notifications.providers.azure_email import AzureCommunicationEmailProvider
from sqlalchemy import select

from koinon.catalog.errors import AccessDenied
from koinon.communications.observation_entities import (
    DeliveryBindingRecord,
    DeliveryInspectionRecord,
    DeliveryObservationRecord,
)
from koinon.communications.observation_repository import (
    DeliveryBindingRepository,
    DeliveryInspectionRepository,
    DeliveryObservationRepository,
)
from koinon.communications.operator_contacts import digest
from koinon.communications.recovery import WelcomeRecoveryService
from koinon.communications.recovery_dtos import (
    DeliveryObservationPage,
    DeliveryOperationObservation,
    DeliveryRecoveryOptions,
)
from koinon.communications.repositories import OutboxRepository
from koinon.security.authority import primary_authority


@service(name="communications.email_operation_observations")
class EmailOperationObservations:
    def __init__(
        self,
        container: Container,
        config: Config,
        bindings: DeliveryBindingRepository,
        inspections: DeliveryInspectionRepository,
        observations: DeliveryObservationRepository,
        authority: WelcomeRecoveryService,
        outbox: OutboxRepository,
    ):
        self.container, self.config, self.bindings = container, config, bindings
        self.inspections, self.observations, self.authority, self.outbox = (
            inspections,
            observations,
            authority,
            outbox,
        )

    def current(self):
        try:
            provider = self.container.resolve(EmailProvider)
        except NoSuchBeanError:
            raise ServiceUnavailableException(
                "Provider operation lookup is unavailable", code="EMAIL_OPERATION_LOOKUP_UNAVAILABLE"
            ) from None
        if (
            not email_capabilities(provider).operation_lookup
            or not isinstance(provider, EmailOperationProvider)
            or provider.name != "azure-communication-email"
            or self.config.get("pyfly.notifications.email.provider") != provider.name
        ):
            raise ServiceUnavailableException(
                "Provider operation lookup is unavailable", code="EMAIL_OPERATION_LOOKUP_UNAVAILABLE"
            )
        endpoint = self.config.get("pyfly.notifications.email.azure.endpoint", "")
        value = urlsplit(endpoint)
        if (
            value.scheme != "https"
            or not value.hostname
            or value.username
            or value.password
            or value.query
            or value.fragment
            or value.path not in ("", "/")
        ):
            raise ServiceUnavailableException(
                "Provider operation identity is unavailable", code="EMAIL_PROVIDER_BINDING_REQUIRED"
            )
        origin = "https://" + value.netloc.lower()
        return provider, digest([provider.name, origin])

    async def _bind(self, row, source, evidence=None):
        provider, instance = self.current()
        previous = await self.bindings.find_by_id(row.id)
        operation = AzureCommunicationEmailProvider.operation_id(row.id)
        if previous:
            if (
                previous.provider != provider.name
                or previous.instance_sha256 != instance
                or previous.operation_id != operation
            ):
                raise AccessDenied("Provider identity changed", code="EMAIL_PROVIDER_BINDING_CHANGED")
            return previous
        return await self.bindings.save(
            DeliveryBindingRecord(
                id=row.id,
                tenant_id=row.tenant_id,
                provider=provider.name,
                instance_sha256=instance,
                operation_id=operation,
                source=source,
                evidence_sha256=evidence,
                created_at=await self.outbox.clock(),
            )
        )

    async def bind_dispatch(self, row):
        try:
            self.current()
        except ServiceUnavailableException:
            return None
        return await self._bind(row, "dispatch")

    @transactional(datasource="primary")
    async def bind_legacy(self, identifier, expected_reference, evidence_sha256):
        await self.authority.operator_contacts._operator()
        row = await self.outbox.find_by_id(identifier)
        if row is None or row.status not in {"unknown", "sent", "failed"}:
            raise AccessDenied("Delivery is unavailable", code="DELIVERY_UNAVAILABLE")
        await self.authority.catalog._lock_tenant(row.tenant_id)
        operation = AzureCommunicationEmailProvider.operation_id(row.id)
        if (
            not re.fullmatch("[a-f0-9]{64}", evidence_sha256)
            or row.provider_reference != expected_reference
            or expected_reference != sha256(operation.encode()).hexdigest()
        ):
            raise AccessDenied(
                "Original provider correlation changed", code="EMAIL_PROVIDER_BINDING_REQUIRED"
            )
        return await self._bind(row, "operator_historical", evidence_sha256)

    async def _binding(self, row):
        provider, instance = self.current()
        binding = await self.bindings.find_by_id(row.id)
        if binding is None:
            raise AccessDenied(
                "The original provider must be verified by an operator",
                code="EMAIL_PROVIDER_BINDING_REQUIRED",
            )
        if (
            binding.tenant_id != row.tenant_id
            or binding.provider != provider.name
            or binding.instance_sha256 != instance
        ):
            raise AccessDenied(
                "The original provider configuration changed", code="EMAIL_PROVIDER_BINDING_CHANGED"
            )
        return provider, binding

    async def _view(self, request):
        observed = await self.observations.find_by_id(request.id)
        if observed:
            return DeliveryOperationObservation(
                id=observed.id,
                delivery_id=request.delivery_id,
                operation_state=observed.operation_state,
                reason_code=observed.reason_code,
                checked_at=observed.checked_at,
            )
        expired = (await self.outbox.clock()).astimezone(UTC) >= request.lease_until
        return DeliveryOperationObservation(
            id=request.id,
            delivery_id=request.delivery_id,
            operation_state="unavailable" if expired else "checking",
            reason_code="EMAIL_INSPECTION_EXPIRED" if expired else None,
        )

    @transactional(datasource="primary")
    async def _claim(self, actor, tenant_id, identifier, generation, key, *, operator=False):
        if operator:
            await self.authority.operator_contacts._operator()
        else:
            await self.authority._administrator(actor, tenant_id, self._token())
        await self.authority.catalog._lock_tenant(tenant_id)
        row = await self.outbox.find_by_id(identifier)
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("Delivery is unavailable", code="DELIVERY_UNAVAILABLE")
        provider, binding = await self._binding(row)
        if (
            not isinstance(key, str)
            or not 1 <= len(key) <= 64
            or any(ord(c) < 33 or ord(c) > 126 for c in key)
        ):
            raise InvalidRequestException(
                "Provide a bounded Idempotency-Key", code="EMAIL_INSPECTION_IDEMPOTENCY_REQUIRED"
            )
        key_hash = sha256(key.encode()).hexdigest()
        body_hash = digest([actor, operator, identifier, generation])
        existing = await self.inspections.find_all(tenant_id=tenant_id, request_key=key_hash)
        if existing:
            if existing[0].request_hash != body_hash:
                raise ConflictException("Inspection key was already used", code="EMAIL_INSPECTION_CONFLICT")
            return existing[0], False
        if row.generation != generation or row.status in {"queued", "preparing", "sending", "deferred"}:
            raise ConflictException("Reload the delivery", code="EMAIL_DELIVERY_CHANGED")
        now = (await self.outbox.clock()).astimezone(UTC)
        recent = await self.inspections._require_session().scalar(
            select(DeliveryInspectionRecord.id)
            .where(
                DeliveryInspectionRecord.delivery_id == identifier, DeliveryInspectionRecord.lease_until > now
            )
            .limit(1)
        )
        if recent:
            raise ConflictException("Wait before another provider check", code="EMAIL_INSPECTION_THROTTLED")
        return await self.inspections.save(
            DeliveryInspectionRecord(
                id=str(uuid4()),
                tenant_id=tenant_id,
                delivery_id=identifier,
                generation=generation,
                request_key=key_hash,
                request_hash=body_hash,
                requested_by=actor,
                authority_kind="operator" if operator else "administrator",
                origin_token_id=None if operator else self._token(),
                created_at=now,
                lease_until=now + timedelta(seconds=30),
            )
        ), True

    @staticmethod
    def _token():
        from pyfly.security.context_holder import SecurityContextHolder

        context = SecurityContextHolder.get_context()
        return context.attributes.get("koinon_token_id") if context else None

    @transactional(datasource="primary")
    async def _finish(self, actor, request, state, code):
        await self._inspection_authority(request)
        row = await self.outbox.find_by_id(request.delivery_id)
        await self._binding(row)
        now = (await self.outbox.clock()).astimezone(UTC)
        if row.generation != request.generation or now >= request.lease_until:
            state, code = "unavailable", "EMAIL_DELIVERY_CHANGED"
        await self.observations.save(
            DeliveryObservationRecord(
                id=request.id,
                tenant_id=request.tenant_id,
                delivery_id=request.delivery_id,
                operation_state=state,
                reason_code=code,
                checked_at=now,
            )
        )
        return await self._view(request)

    async def inspect(self, actor, tenant_id, identifier, generation, key, *, operator=False):
        if current_unit_of_work("primary") is not None:
            raise RuntimeError("Provider inspection requires no ambient primary transaction")
        request, claimed = await self._claim(actor, tenant_id, identifier, generation, key, operator=operator)
        if not claimed:
            return await self._read_view(actor, request)
        row = await self._read_delivery(identifier)
        provider, binding = await self._read_binding(row)
        state, code = "unavailable", "EMAIL_STATUS_UNAVAILABLE"
        try:
            async with asyncio.timeout(12):
                result = await provider.get_status(row.id, binding.operation_id)
            if (
                result.id == row.id
                and result.provider == binding.provider
                and result.provider_id == binding.operation_id
            ):
                state = {
                    EmailStatus.SENT: "accepted",
                    EmailStatus.DELIVERED: "accepted",
                    EmailStatus.FAILED: "rejected",
                    EmailStatus.QUEUED: "pending",
                    EmailStatus.UNKNOWN: "unknown",
                }.get(result.status, "unknown")
                code = (
                    result.error
                    if result.error
                    in {
                        "EMAIL_STATUS_UNAVAILABLE",
                        "EMAIL_INVALID_OPERATION",
                        "EMAIL_INVALID_PROVIDER_RECEIPT",
                        "EMAIL_SEND_REJECTED",
                    }
                    else None
                )
        except asyncio.CancelledError:
            try:
                async with asyncio.timeout(2):
                    await self._finish(actor, request, "unavailable", "EMAIL_INSPECTION_CANCELLED")
            except Exception:
                pass
            raise
        except Exception:
            pass
        return await self._finish(actor, request, state, code)

    @primary_authority()
    async def _read_delivery(self, identifier):
        return await self.outbox.find_by_id(identifier)

    @primary_authority()
    async def _read_binding(self, row):
        return await self._binding(row)

    @primary_authority(fresh=True)
    async def _read_view(self, actor, request):
        await self._inspection_authority(request)
        return await self._view(request)

    @primary_authority(fresh=True)
    async def options(self, actor, tenant_id, identifier):
        await self.authority._administrator(actor, tenant_id, self._token())
        row = await self.outbox.find_by_id(identifier)
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("Delivery is unavailable", code="DELIVERY_UNAVAILABLE")
        can_inspect, inspection_reason, binding_state = False, None, "verified"
        try:
            await self._binding(row)
            can_inspect = row.status not in {"queued", "preparing", "sending", "deferred"}
            if not can_inspect:
                inspection_reason = "EMAIL_DELIVERY_CHANGED"
        except (AccessDenied, ServiceUnavailableException) as error:
            inspection_reason = error.code
            binding_state = (
                "operator_verification_required"
                if error.code == "EMAIL_PROVIDER_BINDING_REQUIRED"
                else "unavailable"
            )
        contact, reason = None, "WELCOME_RECOVERY_NOT_WELCOME"
        if row.kind == "welcome" and not row.event_json.get("welcome_recovery_id"):
            try:
                contact, reason = await self.authority.recovery_options(actor, tenant_id, identifier)
            except ServiceUnavailableException:
                reason = "COMMUNICATIONS_NOT_READY"
        return DeliveryRecoveryOptions(
            delivery_id=row.id,
            generation=row.generation,
            submission_status=row.status,
            attempt_count=row.attempt_count,
            can_inspect=can_inspect,
            inspection_reason=inspection_reason,
            provider_binding_state=binding_state,
            can_recover_welcome=contact is not None,
            recovery_reason=reason,
            contact_id=contact.id if contact else None,
            contact_revision=contact.revision if contact else None,
        )

    @primary_authority(fresh=True)
    async def history(self, actor, tenant_id, identifier):
        await self.authority._administrator(actor, tenant_id, self._token())
        row = await self.outbox.find_by_id(identifier)
        if row is None or row.tenant_id != tenant_id:
            raise AccessDenied("Delivery is unavailable", code="DELIVERY_UNAVAILABLE")
        requests = list(
            await self.inspections._require_session().scalars(
                select(DeliveryInspectionRecord)
                .where(
                    DeliveryInspectionRecord.tenant_id == tenant_id,
                    DeliveryInspectionRecord.delivery_id == identifier,
                )
                .order_by(DeliveryInspectionRecord.created_at.desc(), DeliveryInspectionRecord.id)
                .limit(26)
            )
        )
        return DeliveryObservationPage(
            items=[await self._view(item) for item in requests[:25]], has_more=len(requests) > 25
        )

    async def operator_inspect(self, identifier, generation, key):
        from koinon.communications.operator_contacts import ACTOR

        row = await self._read_delivery(identifier)
        if row is None:
            raise AccessDenied("Delivery is unavailable", code="DELIVERY_UNAVAILABLE")
        return await self.inspect(ACTOR, row.tenant_id, identifier, generation, key, operator=True)

    async def _inspection_authority(self, request):
        if request.authority_kind == "operator":
            await self.authority.operator_contacts._operator()
        else:
            await self.authority._administrator(
                request.requested_by, request.tenant_id, request.origin_token_id
            )
