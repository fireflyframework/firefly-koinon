# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from uuid import uuid4

import pytest
from pyfly.core import Config
from pyfly.notifications import EmailStatus, NotificationResult
from pyfly.notifications.capabilities import EmailProviderCapabilities
from pyfly.notifications.ports import EmailProvider
from test_email_invitations import ACTOR
from test_email_invitations import email_context as email_context
from test_welcome_recovery import prepared

from koinon.communications.observation_repository import (
    DeliveryBindingRepository,
    DeliveryInspectionRepository,
    DeliveryObservationRepository,
)
from koinon.communications.observations import EmailOperationObservations
from koinon.communications.recovery_repository import WelcomeRecoveryRepository
from koinon.communications.repositories import OutboxRepository


class Provider:
    name = "azure-communication-email"
    capabilities = EmailProviderCapabilities(real_delivery=True, inline_cid=True, operation_lookup=True)

    def __init__(self, status=EmailStatus.UNKNOWN):
        self.status = status
        self.reads = []
        self.sends = 0

    async def get_status(self, message_id, operation_id=None):
        self.reads.append((message_id, operation_id))
        return NotificationResult(
            message_id,
            self.name,
            self.status,
            provider_id=operation_id,
            error="EMAIL_STATUS_UNAVAILABLE" if self.status == EmailStatus.UNKNOWN else None,
        )

    async def send(self, *args):
        self.sends += 1
        raise AssertionError("Sending forbidden during operation inspection")


async def observation_service(context, authority, provider):
    for kind in (DeliveryBindingRepository, DeliveryInspectionRepository, DeliveryObservationRepository):
        context.register_bean(kind)
    context.container.register_instance(EmailProvider, provider)
    config = Config(
        {
            "pyfly": {
                "notifications": {
                    "email": {
                        "provider": provider.name,
                        "azure": {"endpoint": "https://owned.communication.azure.com"},
                    }
                }
            }
        }
    )
    return EmailOperationObservations(
        context.container,
        config,
        context.get_bean(DeliveryBindingRepository),
        context.get_bean(DeliveryInspectionRepository),
        context.get_bean(DeliveryObservationRepository),
        authority,
        context.get_bean(OutboxRepository),
    )


async def test_legacy_binding_is_operator_only_and_inspection_never_sends_or_changes_unknown(email_context):
    context, _ = email_context
    authority, target, original = await prepared(context, correlate=True)
    provider = Provider(EmailStatus.SENT)
    service = await observation_service(context, authority, provider)
    before = (original.status, original.attempt_count, original.payload_hash)
    with pytest.raises(Exception) as missing:
        await service.inspect(ACTOR, "north", original.id, original.generation, str(uuid4()))
    assert getattr(missing.value, "code", None) == "EMAIL_PROVIDER_BINDING_REQUIRED"
    await service.bind_legacy(original.id, original.provider_reference, "a" * 64)
    key = str(uuid4())
    result = await service.inspect(ACTOR, "north", original.id, original.generation, key)
    assert result.operation_state == "accepted" and result.recipient_state == "not_observed"
    assert (await service.inspect(ACTOR, "north", original.id, original.generation, key)).id == result.id
    assert provider.reads == [(original.id, original.id)] and provider.sends == 0
    saved = await context.get_bean(OutboxRepository).find_by_id(original.id)
    assert (saved.status, saved.attempt_count, saved.payload_hash) == before
    assert not await context.get_bean(WelcomeRecoveryRepository).find_all()


async def test_unknown_provider_result_stays_unknown_and_changed_instance_is_rejected(email_context):
    from koinon.catalog.errors import AccessDenied

    context, _ = email_context
    authority, target, original = await prepared(context, correlate=True)
    provider = Provider()
    service = await observation_service(context, authority, provider)
    await service.bind_legacy(original.id, original.provider_reference, "a" * 64)
    result = await service.inspect(ACTOR, "north", original.id, original.generation, str(uuid4()))
    assert result.operation_state == "unknown" and result.reason_code == "EMAIL_STATUS_UNAVAILABLE"
    other = Config(
        {
            "pyfly": {
                "notifications": {
                    "email": {
                        "provider": provider.name,
                        "azure": {"endpoint": "https://other.communication.azure.com"},
                    }
                }
            }
        }
    )
    service.config = other
    with pytest.raises(AccessDenied):
        await service.inspect(ACTOR, "north", original.id, original.generation, str(uuid4()))
    assert len(provider.reads) == 1 and provider.sends == 0


async def test_lookup_cancellation_preserves_original_and_never_replays_provider(email_context):
    import asyncio

    context, _ = email_context
    authority, target, original = await prepared(context, correlate=True)
    started = asyncio.Event()
    cleaned = asyncio.Event()

    class Blocking(Provider):
        async def get_status(self, *args):
            self.reads.append(args)
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cleaned.set()

    provider = Blocking()
    service = await observation_service(context, authority, provider)
    await service.bind_legacy(original.id, original.provider_reference, "a" * 64)
    key = str(uuid4())
    task = asyncio.create_task(service.inspect(ACTOR, "north", original.id, original.generation, key))
    await asyncio.wait_for(started.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cleaned.is_set() and provider.sends == 0 and len(provider.reads) == 1
    replay = await service.inspect(ACTOR, "north", original.id, original.generation, key)
    assert replay.operation_state == "unavailable" and len(provider.reads) == 1
    assert (await context.get_bean(OutboxRepository).find_by_id(original.id)).status == "unknown"


async def test_lookup_result_requires_fresh_admin_and_is_not_published_after_revocation(email_context):
    from koinon.catalog.errors import AccessDenied
    from koinon.catalog.repositories import MembershipRepository

    context, _ = email_context
    authority, target, original = await prepared(context, correlate=True)

    class Revoking(Provider):
        async def get_status(self, message_id, operation_id=None):
            row = (await context.get_bean(MembershipRepository).find_all(tenant_id="north", subject=ACTOR))[0]
            row.active = False
            await context.get_bean(MembershipRepository).save(row)
            return await super().get_status(message_id, operation_id)

    provider = Revoking(EmailStatus.SENT)
    service = await observation_service(context, authority, provider)
    await service.bind_legacy(original.id, original.provider_reference, "a" * 64)
    with pytest.raises(AccessDenied):
        await service.inspect(ACTOR, "north", original.id, original.generation, str(uuid4()))
    assert not await service.observations.find_all() and provider.sends == 0
