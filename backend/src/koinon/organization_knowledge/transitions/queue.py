# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from datetime import timedelta

from pyfly.container import service
from pyfly.data.relational.sqlalchemy import LockMode, transactional
from pyfly.kernel import ConflictException
from pyfly.security.context import SecurityContext
from pyfly.security.context_holder import SecurityContextHolder
from sqlalchemy import and_, or_, select

from koinon.jobs.entities import Job
from koinon.organization_knowledge.transitions.entities import KnowledgeModeTransition, now
from koinon.organization_knowledge.transitions.service import KnowledgeModeTransitions


@contextmanager
def original_actor(row):
    attributes = {"koinon_token_id": row.access_token_id} if row.access_token_id else {}
    with SecurityContextHolder.using(SecurityContext(user_id=row.actor, attributes=attributes)):
        yield


@service(name="organization_knowledge.mode_queue")
class ModeTransitionQueue:
    def __init__(self, transitions: KnowledgeModeTransitions):
        self.transitions = transitions

    async def synchronize_cancelled(self):
        for row in await self.transitions.records.cancelled_jobs():
            await self.transitions.synchronize_cancelled(row.tenant_id, row.id)
        for row in await self.transitions.records.cancelled_children():
            await self.transitions.settle_cancelled_children(row.tenant_id, row.id)

    @transactional
    async def claim(self, worker_id, lease_seconds=120):
        if not worker_id or type(lease_seconds) is not int or not 60 <= lease_seconds <= 3600:
            raise ValueError("A worker identity and bounded preparation lease are required")
        moment = now()
        row = await self.transitions.records._require_session().scalar(
            select(KnowledgeModeTransition)
            .join(Job, Job.id == KnowledgeModeTransition.job_id)
            .where(
                Job.kind == "knowledge.mode",
                KnowledgeModeTransition.status.in_(("queued", "running")),
                KnowledgeModeTransition.active_slot == KnowledgeModeTransition.tenant_id,
                or_(
                    and_(Job.status == "queued", Job.available_at <= moment),
                    and_(Job.status == "running", Job.lease_until < moment),
                ),
            )
            .order_by(Job.created_at, Job.id)
            .limit(1)
            .with_for_update(of=KnowledgeModeTransition, skip_locked=True)
        )
        if row is None:
            return None
        job = await self.transitions.jobs._locked(row.tenant_id, row.job_id)
        if job.attempts >= job.max_attempts:
            row.status, row.error_code = "failed", "KNOWLEDGE_MODE_WORKER_EXHAUSTED"
            row.error = "Preparation stopped after repeated interrupted attempts. Review and retry."
            job.status, job.error, job.lease_until = "failed", row.error_code, None
            row.revision += 1
            row.updated_at = moment
            await self.transitions.records.save(row)
            await self.transitions.jobs.repository.save(job)
            return None
        job.status, job.worker_id = "running", worker_id
        job.attempts += 1
        job.lease_until = moment + timedelta(seconds=lease_seconds)
        row.status, row.updated_at = "running", moment
        row.revision += 1
        await self.transitions.records.save(row)
        await self.transitions.jobs.repository.save(job)
        return row.id

    @transactional
    async def fence(self, tenant_id, identifier, worker_id):
        await self.transitions.settings.catalog._lock_tenant(tenant_id)
        row = await self.transitions.records.find_by_id(identifier, lock=LockMode.PESSIMISTIC_WRITE)
        if (
            row is None
            or row.tenant_id != tenant_id
            or row.status != "running"
            or row.active_slot != tenant_id
        ):
            raise ConflictException("Preparation no longer owns its target", code="KNOWLEDGE_MODE_LEASE_LOST")
        job = await self.transitions.jobs._locked(tenant_id, row.job_id, worker_id)
        return row, job

    @transactional
    async def authorize(self, tenant_id, identifier, worker_id):
        row, _ = await self.fence(tenant_id, identifier, worker_id)
        with original_actor(row):
            await self.transitions.authority(row.actor, tenant_id)
            snapshot = await self.transitions.settings.snapshot(row.actor, tenant_id)
        if snapshot.revision != row.base_revision or snapshot.digest != row.base_digest:
            raise ConflictException(
                "Newer knowledge settings superseded preparation", code="KNOWLEDGE_MODE_SUPERSEDED"
            )
        return row

    @transactional
    async def fail(self, tenant_id, identifier, worker_id, *, code):
        row, job = await self.fence(tenant_id, identifier, worker_id)
        row.status = "superseded" if code == "KNOWLEDGE_MODE_SUPERSEDED" else "failed"
        if row.status == "superseded":
            row.active_slot = None
        row.error_code = (
            code if isinstance(code, str) and code.isupper() and len(code) <= 64 else "KNOWLEDGE_MODE_FAILED"
        )
        row.error = (
            "Preparation did not finish. The active mode is unchanged; review the prerequisite and retry."
        )
        row.updated_at = now()
        row.revision += 1
        job.status, job.error = "failed", row.error_code
        job.lease_until, job.worker_id = None, None
        await self.transitions.records.save(row)
        await self.transitions.jobs.repository.save(job)
