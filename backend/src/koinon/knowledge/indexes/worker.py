# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native scheduled bounded batches with durable leases and original-actor authority."""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from uuid import uuid4

from pyfly.container import component, service
from pyfly.core import config_properties
from pyfly.data.relational.sqlalchemy import LockMode
from pyfly.kernel import ConflictException
from pyfly.scheduling import scheduled
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.connections.service import embedding_fingerprint
from koinon.knowledge.indexes.lifecycle import IndexLifecycleService
from koinon.knowledge.indexes.queue import IndexQueue
from koinon.knowledge.indexes.transactions import require_detached_provider_work
from koinon.security.authority import primary_authority
from koinon.workers.admission import WorkAdmission

logger = logging.getLogger(__name__)


@component(name="knowledge.index_worker_settings")
@config_properties(prefix="koinon.knowledge.indexes")
@dataclass
class IndexWorkerSettings:
    enabled: bool = False
    batch_timeout_seconds: int = 45
    lease_seconds: int = 120

    def validate(self):
        if (
            type(self.batch_timeout_seconds) is not int
            or not 1 <= self.batch_timeout_seconds <= 90
            or type(self.lease_seconds) is not int
            or not 60 <= self.lease_seconds <= 3600
            or self.lease_seconds < self.batch_timeout_seconds + 30
        ):
            raise ValueError("The index lease must exceed its bounded batch timeout by at least 30 seconds")


@service(name="knowledge.index_worker")
class IndexWorker:
    def __init__(
        self,
        lifecycle: IndexLifecycleService,
        queue: IndexQueue,
        settings: IndexWorkerSettings,
        admission: WorkAdmission,
    ):
        self.lifecycle, self.queue, self.settings = lifecycle, queue, settings
        self.admission = admission
        self.worker_id = "index-" + uuid4().hex

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        if not self.settings.enabled:
            return
        self.settings.validate()
        async with self.admission.hold("index"):
            await self._one()

    async def _one(self):
        job_id = await self.queue.claim(self.worker_id, self.settings.lease_seconds)
        if job_id is None:
            return
        job = await self.queue.jobs.repository.find_by_id(job_id)
        try:
            async with asyncio.timeout(self.settings.batch_timeout_seconds):
                await self.execute(job_id)
        except Exception as error:
            code = str(getattr(error, "code", None) or "INDEX_BATCH_FAILED")[:64]
            logger.warning(
                "Index batch failed",
                extra={
                    "job_id": job_id,
                    "error_code": code,
                    "error_type": type(error).__name__,
                },
            )
            try:
                await self.queue.failed(job.tenant_id, job_id, self.worker_id, code=code)
            except Exception as failure:
                if getattr(failure, "code", None) not in {"JOB_LEASE_LOST", "INDEX_LEASE_LOST"}:
                    raise

    @asynccontextmanager
    async def publication(self, job_id, *, expected_revision=None):
        require_detached_provider_work()
        observed = await self.queue.jobs.repository.find_by_id(job_id)
        if observed is None:
            raise ValueError("The durable index target is unavailable")
        catalog = self.lifecycle.reader.facade.catalog
        async with primary_authority(read_only=False):
            await catalog._lock_tenant(observed.tenant_id)
            await self.lifecycle.check_parent(
                observed.tenant_id, observed.payload.get("parent_mode_transition_id")
            )
            job, record = await self.queue.fence(observed.tenant_id, observed.id, self.worker_id)
            if expected_revision is not None and record.revision != expected_revision:
                raise ConflictException("The target changed during embedding", code="INDEX_REVISION_CONFLICT")
            attributes = {"koinon_token_id": record.access_token_id} if record.access_token_id else {}
            actor = record.updated_by
            with SecurityContextHolder.using(SecurityContext(user_id=actor, attributes=attributes)):
                members = await catalog.membership_repository.find_all(
                    subject=actor, tenant_id=record.tenant_id, active=True
                )
                for member in sorted(members, key=lambda value: value.id):
                    await catalog.membership_repository.find_by_id(member.id, lock=LockMode.PESSIMISTIC_READ)
                if record.access_token_id:
                    if catalog.restriction is None:
                        raise ValueError("The submitting API token cannot be revalidated")
                    await catalog.restriction.tokens.find_by_id(
                        record.access_token_id, lock=LockMode.PESSIMISTIC_READ
                    )
                await self.lifecycle.scoped(actor, record.tenant_id, record.id, write=True)
                await self.lifecycle.check_parent(
                    record.tenant_id, job.payload.get("parent_mode_transition_id"), record
                )
                provider = await self.lifecycle.reader.planner.provider(
                    record.tenant_id, record.provider_id, record.model_id
                )
                if (
                    provider.revision != record.provider_revision
                    or record.embedding_fingerprint
                    != embedding_fingerprint(
                        provider, record.model_id, record.dimensions, record.storage_dimensions
                    )
                ):
                    raise ConflictException(
                        "The selected embedding connection changed; review and resume the preserved target",
                        code="INDEX_PROVIDER_CHANGED",
                    )
                yield job, record, provider

    async def execute(self, job_id):
        async with self.publication(job_id) as (job, record, provider):
            revision = record.revision
        native = "canon" if record.domain == "documents" else "structured"
        port = import_module(
            ("flycanon" if native == "canon" else "flyquery") + ".core.agents.model_bindings"
        )
        actor = record.updated_by
        attributes = {"koinon_token_id": record.access_token_id} if record.access_token_id else {}

        @asynccontextmanager
        async def guard():
            async with self.publication(job_id, expected_revision=revision):
                yield

        async def fence():
            await self.queue.fence(record.tenant_id, job.id, self.worker_id)

        with (
            SecurityContextHolder.using(SecurityContext(user_id=actor, attributes=attributes)),
            native_scope(native, record.tenant_id, record.native_workspace_id, actor),
        ):
            async with self.lifecycle.reader.planner.open(
                provider, record.model_id, record.dimensions
            ) as embedder:
                binding = port.EmbeddingBinding(
                    embedder,
                    f"{provider.kind}:{record.model_id}",
                    record.dimensions,
                    record.storage_dimensions,
                    record.native_id,
                    **({"versioned": True} if native == "structured" else {}),
                )
                token = port.push_bindings(
                    tenant_id=record.tenant_id,
                    workspace_id=record.native_workspace_id,
                    subject=actor,
                    bindings={},
                    embeddings={record.domain + ".embedding": binding},
                )
                try:
                    result = await self.lifecycle.reader.adapter.step(
                        record, embedder=embedder, validate_write=fence, publication_guard=guard
                    )
                finally:
                    port.reset_bindings(token)
        async with guard():
            await self.queue.progress(record.tenant_id, job.id, self.worker_id, result)


async def run_worker():
    from koinon.worker import run_worker as complete_worker

    await complete_worker()


if __name__ == "__main__":
    asyncio.run(run_worker())
