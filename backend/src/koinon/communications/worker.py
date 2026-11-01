# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The native worker scheduler consumes bounded communications under the shared budget."""

from datetime import timedelta
from uuid import uuid4

from pyfly.container import service
from pyfly.context.conditions import conditional_on_property
from pyfly.scheduling import scheduled

from koinon.communications.digest import DigestScheduler
from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.settings import CommunicationsSettings
from koinon.communications.submission import EmailSubmission
from koinon.workers.admission import WorkAdmission


@service(name="communications.worker")
@conditional_on_property("koinon.process.role", having_value="worker")
class CommunicationsWorker:
    def __init__(
        self,
        state: CommunicationOutbox,
        submission: EmailSubmission,
        settings: CommunicationsSettings,
        admission: WorkAdmission,
        digests: DigestScheduler | None = None,
    ):
        self.state, self.submission, self.settings, self.admission = state, submission, settings, admission
        self.digests = digests
        self.worker_id = "communications-" + uuid4().hex
        self._running = False

    @scheduled(fixed_delay=timedelta(seconds=15))
    async def tick(self):
        if not self.settings.enabled or self._running:
            return
        self._running = True
        try:
            if self.digests is not None:
                async with self.admission.hold("communications"):
                    await self.digests.reconcile()
                    await self.digests.admit_due()
            for _ in range(10):
                async with self.admission.hold("communications"):
                    ticket = await self.state.claim(self.worker_id)
                    if ticket is None:
                        return
                    await self.submission.execute(ticket)
        finally:
            self._running = False
