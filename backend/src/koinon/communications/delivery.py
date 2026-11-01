# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native transport submission follows the durable sending fence; ambiguity is terminal."""

import asyncio
from hashlib import sha256

from pyfly.container import Container, service
from pyfly.notifications import EmailMessage, EmailStatus
from pyfly.notifications.services import DefaultEmailService

from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.settings import CommunicationsSettings


@service(name="communications.dispatcher")
class EmailDispatcher:
    def __init__(self, container: Container, settings: CommunicationsSettings, state: CommunicationOutbox):
        self.container, self.settings, self.state = container, settings, state

    async def send(self, ticket, message: EmailMessage):
        status, code, reference = "unknown", "SEND_OUTCOME_UNKNOWN", None
        try:
            transport = self.container.resolve(DefaultEmailService)
            async with asyncio.timeout(self.settings.send_timeout_seconds):
                result = await transport.send(message)
            if result.id == message.id:
                if result.status in {EmailStatus.SENT, EmailStatus.DELIVERED}:
                    status, code = "sent", None
                elif result.status == EmailStatus.FAILED:
                    status, code = "failed", "PROVIDER_REJECTED"
                elif result.status == EmailStatus.SUPPRESSED:
                    status, code = "suppressed", "PROVIDER_SUPPRESSED"
                if result.provider_id:
                    reference = sha256(result.provider_id.encode()).hexdigest()
        except asyncio.CancelledError:
            await asyncio.shield(self.state.complete(ticket, "unknown", failure_code="SEND_OUTCOME_UNKNOWN"))
            raise
        except Exception:
            # Native providers redact diagnostics; only a fixed public outcome code is retained.
            pass
        await self.state.complete(ticket, status, failure_code=code, provider_reference=reference)
