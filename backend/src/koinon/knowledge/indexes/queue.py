# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Kind-filtered native leases; a successful bounded batch is not a failed attempt."""

from datetime import UTC, datetime, timedelta

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException
from sqlalchemy import and_, or_, select

from koinon.jobs.entities import Job
from koinon.jobs.service import JobService
from koinon.knowledge.indexes.entities import KnowledgeIndex, timestamp
from koinon.knowledge.indexes.repositories import KnowledgeIndexRepository


@service(name="knowledge.index_queue")
class IndexQueue:
    def __init__(self, records: KnowledgeIndexRepository, jobs: JobService):
        self.records, self.jobs = records, jobs

    @transactional
    async def claim(self, worker_id, lease_seconds=120):
        if not worker_id or not 60 <= lease_seconds <= 3600:
            raise ValueError("A worker identity and bounded native lease are required")
        session = self.records._require_session()
        now = timestamp()
        cancelled = await session.scalars(
            select(Job)
            .join(KnowledgeIndex, KnowledgeIndex.job_id == Job.id)
            .where(
                Job.kind == "knowledge.index",
                Job.status == "cancelled",
                KnowledgeIndex.status.in_(("queued", "building", "awaiting_index")),
            )
            .order_by(Job.created_at, Job.id)
            .limit(25)
            .with_for_update(of=Job, skip_locked=True)
        )
        for cancelled_job in cancelled:
            cancelled_row = await self.records.find_by_id(
                cancelled_job.payload["index_id"], lock=LockMode.PESSIMISTIC_WRITE
            )
            cancelled_row.status, cancelled_row.build_slot = "cancelled", None
            cancelled_row.error_code = "INDEX_JOB_CANCELLED"
            cancelled_row.revision += 1
            cancelled_row.updated_at = now
            await self.records.save(cancelled_row)
        job = await session.scalar(
            select(Job)
            .join(KnowledgeIndex, KnowledgeIndex.job_id == Job.id)
            .where(
                Job.kind == "knowledge.index",
                or_(
                    and_(Job.status == "queued", Job.available_at <= now),
                    and_(Job.status == "running", Job.lease_until < now),
                ),
                KnowledgeIndex.status.in_(("queued", "building", "awaiting_index")),
            )
            .order_by(Job.created_at, Job.id)
            .limit(1)
            .with_for_update(of=Job, skip_locked=True)
        )
        if job is None:
            return None
        row = await self.records.find_by_id(job.payload["index_id"], lock=LockMode.PESSIMISTIC_WRITE)
        if job.attempts >= job.max_attempts:
            job.status, job.error, job.lease_until = (
                "failed",
                "Index worker lease/retry budget exhausted",
                None,
            )
            row.status, row.build_slot, row.error_code = "failed", None, "INDEX_WORKER_EXHAUSTED"
            await self.records.save(row)
            await self.jobs.repository.save(job)
            return None
        job.status, job.worker_id = "running", worker_id
        job.attempts += 1
        job.lease_until = now + timedelta(seconds=lease_seconds)
        row.status = "building"
        await self.records.save(row)
        await self.jobs.repository.save(job)
        return job.id

    async def fence(self, tenant_id, job_id, worker_id):
        job = await self.jobs._locked(tenant_id, job_id, worker_id)
        row = await self.records.find_by_id(job.payload["index_id"], lock=LockMode.PESSIMISTIC_WRITE)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.job_id != job.id
            or row.status not in {"building", "awaiting_index"}
        ):
            raise ConflictException("Index work no longer owns its target", code="INDEX_LEASE_LOST")
        return job, row

    @transactional
    async def progress(self, tenant_id, job_id, worker_id, result):
        job, row = await self.fence(tenant_id, job_id, worker_id)
        row.chunk_count, row.vector_count = result["chunk_count"], result["vector_count"]
        row.indexed = result.get("indexed", False)
        done = result["complete"] and row.indexed
        row.status = "ready" if done else "awaiting_index" if result["complete"] else "building"
        row.qualification = (
            "coverage_and_ann_passed" if done else "coverage_passed" if result["complete"] else "building"
        )
        if done:
            row.ready_at, row.build_slot = timestamp(), None
        row.revision += 1
        row.updated_at = timestamp()
        job.status = "succeeded" if done else "queued"
        job.result = {
            "index_id": row.id,
            "status": row.status,
            "chunk_count": row.chunk_count,
            "vector_count": row.vector_count,
        }
        job.progress = 100 if done else min(99, int(100 * row.vector_count / max(1, row.chunk_count)))
        job.lease_until, job.worker_id, job.attempts = None, None, 0
        job.available_at = datetime.now(UTC) + timedelta(seconds=30 if row.status == "awaiting_index" else 0)
        await self.records.save(row)
        await self.jobs.repository.save(job)
        return row

    @transactional
    async def failed(self, tenant_id, job_id, worker_id, *, code):
        job, row = await self.fence(tenant_id, job_id, worker_id)
        job.status = "failed" if job.attempts >= job.max_attempts else "queued"
        job.error = code
        job.available_at = timestamp() + timedelta(seconds=5)
        job.lease_until, job.worker_id = None, None
        row.error_code = code
        row.error = (
            "The embedding provider changed; review its configuration before resuming or creating a version"
            if code == "INDEX_PROVIDER_CHANGED"
            else "The submitting account or API token lost access; restore authorized access before resuming"
            if code
            in {"ACCESS_DENIED", "TOKEN_INVALID", "TOKEN_SCOPE_DENIED", "TOKEN_REVOKED", "TOKEN_UNAVAILABLE"}
            else "Index work failed; inspect the selected connection and retry this preserved target"
        )
        if job.status == "failed":
            row.status, row.build_slot = "failed", None
        await self.records.save(row)
        await self.jobs.repository.save(job)
