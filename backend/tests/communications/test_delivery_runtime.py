# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import asyncio
import contextvars
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pyfly.notifications import EmailMessage, EmailStatus, NotificationResult

from koinon.communications.delivery import EmailDispatcher
from koinon.communications.settings import CommunicationsSettings
from koinon.communications.worker import CommunicationsWorker
from koinon.workers.admission import WorkAdmission, WorkAdmissionSettings, WorkAdmissionUnavailable


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


async def test_capacity_deferral_keeps_digest_and_delivery_unclaimed_until_a_later_tick():
    gate = WorkAdmission(WorkAdmissionSettings(wait_timeout_seconds=0.01))
    state = SimpleNamespace(claim=AsyncMock(return_value=None))
    submission = SimpleNamespace(execute=AsyncMock())
    digests = SimpleNamespace(reconcile=AsyncMock(), admit_due=AsyncMock())
    worker = CommunicationsWorker(state, submission, CommunicationsSettings(enabled=True), gate, digests)
    async with gate.hold("conversation"):
        await asyncio.create_task(worker.tick(), context=contextvars.Context())
    state.claim.assert_not_awaited()
    submission.execute.assert_not_awaited()
    digests.reconcile.assert_not_awaited()
    digests.admit_due.assert_not_awaited()
    assert not worker._running and gate.worker_active == gate.worker_waiting == 0
    await worker.tick()
    state.claim.assert_awaited_once()
    digests.reconcile.assert_awaited_once()
    digests.admit_due.assert_awaited_once()


async def test_capacity_error_after_delivery_admission_is_not_silenced():
    state = SimpleNamespace(claim=AsyncMock(side_effect=WorkAdmissionUnavailable()))
    worker = CommunicationsWorker(
        state, SimpleNamespace(), CommunicationsSettings(enabled=True), WorkAdmission(WorkAdmissionSettings())
    )
    with pytest.raises(WorkAdmissionUnavailable):
        await worker.tick()
    state.claim.assert_awaited_once()
    assert not worker._running


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
