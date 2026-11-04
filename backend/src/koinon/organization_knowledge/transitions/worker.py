# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""One bounded preparation phase per lease; active settings change only at final CAS."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from uuid import uuid4

from pyfly.container import component, service
from pyfly.core import config_properties
from pyfly.data.relational.sqlalchemy import transactional
from pyfly.scheduling import scheduled

from koinon.organization_knowledge.transitions.activation import ModeActivation
from koinon.organization_knowledge.transitions.discovery import ModeDiscovery
from koinon.organization_knowledge.transitions.index_preparation import ModeIndexPreparation
from koinon.organization_knowledge.transitions.preflight import ModePreflight
from koinon.organization_knowledge.transitions.progress import ModeProgress
from koinon.organization_knowledge.transitions.queue import ModeTransitionQueue
from koinon.organization_knowledge.transitions.verification_progress import ModeVerificationProgress
from koinon.organization_knowledge.transitions.view_preparation import ModeViewPreparation
from koinon.workers.admission import WorkAdmission

logger = logging.getLogger(__name__)


@component(name="organization_knowledge.mode_worker_settings")
@config_properties(prefix="koinon.knowledge.mode_preparation")
@dataclass
class ModeWorkerSettings:
    enabled: bool = False
    step_timeout_seconds: int = 90
    lease_seconds: int = 120

    def validate(self):
        if (
            type(self.step_timeout_seconds) is not int
            or not 1 <= self.step_timeout_seconds <= 300
            or type(self.lease_seconds) is not int
            or not 60 <= self.lease_seconds <= 3600
            or self.lease_seconds < self.step_timeout_seconds + 30
        ):
            raise ValueError("The preparation lease must exceed its bounded step timeout by 30 seconds")


@service(name="organization_knowledge.mode_worker")
class ModeWorker:
    def __init__(
        self,
        queue: ModeTransitionQueue,
        discovery: ModeDiscovery,
        preflight: ModePreflight,
        views: ModeViewPreparation,
        indexes: ModeIndexPreparation,
        verification: ModeVerificationProgress,
        activation: ModeActivation,
        progress: ModeProgress,
        settings: ModeWorkerSettings,
        admission: WorkAdmission,
    ):
        self.queue, self.discovery, self.preflight, self.views, self.indexes = (
            queue,
            discovery,
            preflight,
            views,
            indexes,
        )
        self.verification, self.activation, self.progress = verification, activation, progress
        self.settings, self.admission = settings, admission
        self.worker_id = "knowledge-mode-" + uuid4().hex

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        if not self.settings.enabled:
            return
        self.settings.validate()
        async with self.admission.hold("index"):
            await self.queue.synchronize_cancelled()
            identifier = await self.queue.claim(self.worker_id, self.settings.lease_seconds)
            if identifier is None:
                return
            row = await self.queue.transitions.records.find_by_id(identifier)
            try:
                async with asyncio.timeout(self.settings.step_timeout_seconds):
                    await self.execute(row.tenant_id, identifier)
            except Exception as error:
                code = getattr(error, "code", None) or "KNOWLEDGE_MODE_FAILED"
                logger.warning(
                    "Knowledge preparation stopped",
                    extra={"transition_id": identifier, "error_type": type(error).__name__},
                )
                try:
                    if code == "KNOWLEDGE_MODE_GENERATION_CHANGED":
                        await self.verification.restart(row.tenant_id, identifier, self.worker_id)
                    elif code == "KNOWLEDGE_MODE_SCOPE_CHANGED":
                        await self.rediscover(row.tenant_id, identifier)
                    else:
                        await self.queue.fail(row.tenant_id, identifier, self.worker_id, code=code)
                except Exception as failure:
                    if getattr(failure, "code", None) not in {"KNOWLEDGE_MODE_LEASE_LOST", "JOB_LEASE_LOST"}:
                        raise

    async def execute(self, tenant_id, identifier):
        row = await self.queue.authorize(tenant_id, identifier, self.worker_id)
        if row.stage == "discovery":
            await self.discovery.step(tenant_id, identifier, self.worker_id)
            current = await self.queue.authorize(tenant_id, identifier, self.worker_id)
            await self.progress.record(
                tenant_id, identifier, self.worker_id, stage=current.stage, milliseconds=0
            )
        elif row.stage == "preflight":
            await self.preflight.step(tenant_id, identifier, self.worker_id)
        elif row.stage == "repair_views":
            await self.views.step(tenant_id, identifier, self.worker_id)
        elif row.stage == "prepare_indexes":
            await self.indexes.step(tenant_id, identifier, self.worker_id)
        elif row.stage == "verify":
            await self.verification.step(tenant_id, identifier, self.worker_id)
        elif row.stage == "activate":
            await self.activation.activate(tenant_id, identifier, self.worker_id)
        else:
            raise ValueError("Preparation has no supported stage")

    @transactional
    async def rediscover(self, tenant_id, identifier):
        row = await self.queue.authorize(tenant_id, identifier, self.worker_id)
        row.stage, row.cursor = "discovery", {"reconcile_targets": True}
        row.counters = {**row.counters, "scope_restarts": row.counters.get("scope_restarts", 0) + 1}
        await self.queue.transitions.records.save(row)
        await self.progress.record(tenant_id, identifier, self.worker_id, stage="discovery", milliseconds=0)
