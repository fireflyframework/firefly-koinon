# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native scheduled bounded batches with durable leases and original-actor authority."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from uuid import uuid4

from pyfly.container import component, service
from pyfly.core import config_properties
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException
from pyfly.scheduling import scheduled
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.connections.service import embedding_fingerprint
from koinon.knowledge.indexes.lifecycle import IndexLifecycleService
from koinon.knowledge.indexes.queue import IndexQueue

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
    def __init__(self, lifecycle: IndexLifecycleService, queue: IndexQueue, settings: IndexWorkerSettings):
        self.lifecycle, self.queue, self.settings = lifecycle, queue, settings
        self.worker_id = "index-" + uuid4().hex

    @scheduled(fixed_delay=timedelta(seconds=1))
    async def tick(self):
        if not self.settings.enabled:
            return
        self.settings.validate()
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

    @transactional
    async def execute(self, job_id):
        job = await self.queue.jobs.repository.find_by_id(job_id)
        if job is None:
            raise ValueError("The durable index target is unavailable")
        job, record = await self.queue.fence(job.tenant_id, job.id, self.worker_id)
        attributes = {"koinon_token_id": record.access_token_id} if record.access_token_id else {}
        actor = record.updated_by
        with SecurityContextHolder.using(SecurityContext(user_id=actor, attributes=attributes)):
            catalog = self.lifecycle.reader.facade.catalog
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
            planner = self.lifecycle.reader.planner
            provider = await planner.provider(record.tenant_id, record.provider_id, record.model_id)
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
            native = "canon" if record.domain == "documents" else "structured"
            port = import_module(
                ("flycanon" if native == "canon" else "flyquery") + ".core.agents.model_bindings"
            )

            async def fence():
                await self.queue.fence(record.tenant_id, job.id, self.worker_id)
                await self.lifecycle.scoped(actor, record.tenant_id, record.id, write=True)

            with native_scope(native, record.tenant_id, record.native_workspace_id, actor):
                async with planner.open(provider, record.model_id, record.dimensions) as embedder:
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
                            record, embedder=embedder, validate_write=fence
                        )
                    finally:
                        port.reset_bindings(token)
            await self.queue.progress(record.tenant_id, job.id, self.worker_id, result)


async def run_worker():
    from koinon.app import create_application
    from koinon.operations.configuration import environment_configuration

    values = environment_configuration()
    values.setdefault("koinon", {}).setdefault("knowledge", {}).setdefault("indexes", {})["enabled"] = True
    application = create_application(values)
    context = application.state.context
    await context.start()
    try:
        await asyncio.Event().wait()
    finally:
        await context.stop()


if __name__ == "__main__":
    asyncio.run(run_worker())
