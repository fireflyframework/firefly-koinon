# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.notifications import EmailMessage, EmailStatus, NotificationResult

from koinon.communications.delivery import EmailDispatcher
from koinon.communications.settings import CommunicationsSettings
from koinon.communications.worker import CommunicationsWorker


class OwnedAdmission:
    def __init__(self):
        self.held = False

    @asynccontextmanager
    async def hold(self, kind):
        assert kind == "communications"
        self.held = True
        try:
            yield
        finally:
            self.held = False


async def test_shared_admission_covers_claim_and_complete_transport_lifetime():
    admission = OwnedAdmission()
    ticket = SimpleNamespace(id="delivery")

    async def claim(owner):
        assert admission.held
        return ticket if claims.pop() else None

    claims = [False, True]

    async def execute(value):
        assert value is ticket and admission.held

    state = SimpleNamespace(claim=claim)
    worker = CommunicationsWorker(
        state, SimpleNamespace(execute=execute), CommunicationsSettings(enabled=True), admission
    )
    await worker.tick()
    assert not claims and not admission.held


async def test_provider_pending_and_transport_failure_are_unknown_without_automatic_retry():
    message = EmailMessage(
        id="stable-operation",
        to=["person@example.test"],
        sender="team@example.test",
        subject="Subject",
        body_text="Text",
        body_html="<p>Text</p>",
    )
    for outcome in (
        NotificationResult(message.id, "owned", EmailStatus.QUEUED),
        RuntimeError("sensitive provider exception"),
    ):
        state = SimpleNamespace(complete=AsyncMock())

        async def send(value, outcome=outcome):
            assert value is message
            if isinstance(outcome, Exception):
                raise outcome
            return outcome

        dispatcher = EmailDispatcher(
            SimpleNamespace(resolve=lambda kind: SimpleNamespace(send=send)),
            CommunicationsSettings(enabled=True),
            state,
        )
        await dispatcher.send(SimpleNamespace(id="delivery"), message)
        state.complete.assert_awaited_once_with(
            SimpleNamespace(id="delivery"),
            "unknown",
            failure_code="SEND_OUTCOME_UNKNOWN",
            provider_reference=None,
        )
