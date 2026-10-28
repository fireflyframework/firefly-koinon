# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable, leased jobs; callers must authorize the resource before submission."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import DuplicateKeyException, InvalidRequestException

from koinon.jobs.entities import Job
from koinon.jobs.errors import JobConflict
from koinon.jobs.repository import JobRepository
from koinon.operations.settings import OperationalSettings


@service
class JobService:
    def __init__(self, repository: JobRepository, settings: OperationalSettings | None = None):
        self.repository = repository
        self.settings = settings or OperationalSettings()

    async def submit(
        self, tenant_id: str, resource_id: str, kind: str, payload: dict, idempotency_key: str
    ) -> Job:
        if not idempotency_key or len(idempotency_key) > 255:
            raise InvalidRequestException("Idempotency-Key must contain 1 to 255 characters")
        digest = hashlib.sha256(
            json.dumps([resource_id, kind, payload], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        rows = await self.repository.find_all(tenant_id=tenant_id, idempotency_key=idempotency_key)
        if not rows:
            try:
                return await self.repository.save(
                    Job(
                        id=str(uuid4()),
                        tenant_id=tenant_id,
                        resource_id=resource_id,
                        kind=kind,
                        payload=payload,
                        payload_hash=digest,
                        idempotency_key=idempotency_key,
                    )
                )
            except DuplicateKeyException:
                rows = await self.repository.find_all(tenant_id=tenant_id, idempotency_key=idempotency_key)
        if not rows or rows[0].payload_hash != digest:
            raise JobConflict(
                "Idempotency key already belongs to a different request", code="IDEMPOTENCY_CONFLICT"
            )
        return rows[0]

    async def claim(self, worker_id: str, lease_seconds: int | None = None) -> Job | None:
        lease_seconds = self.settings.job_lease_seconds if lease_seconds is None else lease_seconds
        if (
            not worker_id
            or isinstance(lease_seconds, bool)
            or not isinstance(lease_seconds, int)
            or not 1 <= lease_seconds <= 3600
        ):
            raise InvalidRequestException("A worker identity and lease from 1 to 3600 seconds are required")
        return await self.repository.claim(worker_id, lease_seconds)

    async def _locked(self, tenant_id: str, job_id: str, worker_id: str | None = None) -> Job:
        job = await self.repository.find_by_id(job_id, lock=LockMode.PESSIMISTIC_WRITE)
        if job is None or job.tenant_id != tenant_id:
            raise JobConflict("Job is unavailable in this context", code="JOB_UNAVAILABLE")
        if worker_id is not None and (
            job.status != "running"
            or job.worker_id != worker_id
            or job.lease_until is None
            or job.lease_until <= datetime.now(UTC)
        ):
            raise JobConflict("Worker no longer owns a live lease", code="JOB_LEASE_LOST")
        return job

    @transactional
    async def complete(self, tenant_id: str, job_id: str, worker_id: str, result: dict) -> Job:
        job = await self._locked(tenant_id, job_id, worker_id)
        job.status, job.result, job.progress = "succeeded", result, 100
        job.lease_until = None
        job.updated_at = datetime.now(UTC)
        return await self.repository.save(job)

    @transactional
    async def fail(
        self, tenant_id: str, job_id: str, worker_id: str, error: str, retry_delay: int = 30
    ) -> Job:
        job = await self._locked(tenant_id, job_id, worker_id)
        job.status = "queued" if job.attempts < job.max_attempts else "failed"
        job.error = error[:2000]
        job.available_at = datetime.now(UTC) + timedelta(seconds=max(0, retry_delay))
        job.lease_until = None
        job.worker_id = None
        job.updated_at = datetime.now(UTC)
        return await self.repository.save(job)

    @transactional
    async def cancel(self, tenant_id: str, job_id: str) -> Job:
        job = await self._locked(tenant_id, job_id)
        if job.status in ("succeeded", "failed"):
            raise JobConflict("Terminal jobs cannot be cancelled", code="JOB_TERMINAL")
        job.status = "cancelled"
        job.lease_until = None
        job.updated_at = datetime.now(UTC)
        return await self.repository.save(job)
