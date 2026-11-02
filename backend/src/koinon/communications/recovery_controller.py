# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit operation inspection and manually acknowledged new welcome deliveries."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.communications.observations import EmailOperationObservations
from koinon.communications.recovery import WelcomeRecoveryService
from koinon.communications.recovery_dtos import (
    DeliveryInspectionInput,
    DeliveryObservationPage,
    DeliveryOperationObservation,
    DeliveryRecoveryOptions,
    WelcomeRecoveryAcknowledgement,
    WelcomeRecoveryInput,
)
from koinon.security.identity import identity_from_request


@rest_controller(name="communications.delivery_recovery_controller")
@request_mapping("/api/v1")
class DeliveryRecoveryController:
    def __init__(self, observations: EmailOperationObservations, recovery: WelcomeRecoveryService):
        self.observations, self.recovery = observations, recovery

    @get_mapping("/tenants/{tenant_id}/communications/deliveries/{delivery_id}/recovery")
    async def delivery_recovery(
        self, tenant_id: PathVar[str], delivery_id: PathVar[str], request: Request
    ) -> DeliveryRecoveryOptions:
        return await self.observations.options(identity_from_request(request).subject, tenant_id, delivery_id)

    @get_mapping("/tenants/{tenant_id}/communications/deliveries/{delivery_id}/observations")
    async def delivery_observations(
        self, tenant_id: PathVar[str], delivery_id: PathVar[str], request: Request
    ) -> DeliveryObservationPage:
        return await self.observations.history(identity_from_request(request).subject, tenant_id, delivery_id)

    @post_mapping("/tenants/{tenant_id}/communications/deliveries/{delivery_id}/observations")
    async def inspect_delivery(
        self,
        tenant_id: PathVar[str],
        delivery_id: PathVar[str],
        body: Valid[Body[DeliveryInspectionInput]],
        request: Request,
    ) -> DeliveryOperationObservation:
        return await self.observations.inspect(
            identity_from_request(request).subject,
            tenant_id,
            delivery_id,
            body.expected_generation,
            request.headers.get("idempotency-key"),
        )

    @post_mapping("/tenants/{tenant_id}/communications/deliveries/{delivery_id}/welcome-recovery")
    async def recover_welcome(
        self,
        tenant_id: PathVar[str],
        delivery_id: PathVar[str],
        body: Valid[Body[WelcomeRecoveryInput]],
        request: Request,
    ) -> WelcomeRecoveryAcknowledgement:
        return await self.recovery.recover(
            identity_from_request(request).subject,
            tenant_id,
            delivery_id,
            body,
            request.headers.get("idempotency-key"),
        )
