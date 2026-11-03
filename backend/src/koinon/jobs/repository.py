# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from datetime import UTC, datetime, timedelta

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from sqlalchemy import and_, or_, select, update

from koinon.jobs.entities import Job


@repository
class JobRepository(Repository[Job, str]):
    async def claim(self, worker_id: str, lease_seconds: int) -> Job | None:
        session = self._require_session()
        now = datetime.now(UTC)
        ordinary = Job.kind.not_in(
            ["knowledge.bulk.intake", "knowledge.bulk.query", "knowledge.mode", "knowledge.index"]
        )
        expired = and_(ordinary, Job.status == "running", Job.lease_until < now)
        await session.execute(
            update(Job)
            .where(expired, Job.attempts >= Job.max_attempts)
            .values(status="failed", error="Worker lease expired after final attempt", updated_at=now)
        )
        candidate = await session.scalar(
            select(Job)
            .where(
                ordinary,
                or_(and_(Job.status == "queued", Job.available_at <= now), expired),
                Job.attempts < Job.max_attempts,
            )
            .order_by(Job.created_at, Job.id)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if candidate is None:
            return None
        candidate.status = "running"
        candidate.attempts += 1
        candidate.worker_id = worker_id
        candidate.lease_until = now + timedelta(seconds=lease_seconds)
        candidate.updated_at = now
        await session.flush()
        return candidate

    async def cancel_mode_children(self, tenant_id: str, transition_id: str) -> int:
        candidates = (
            select(Job.id)
            .where(
                Job.tenant_id == tenant_id,
                Job.kind == "knowledge.index",
                Job.payload["parent_mode_transition_id"].as_string() == transition_id,
                Job.status.in_(("queued", "running")),
            )
            .order_by(Job.id)
            .limit(25)
        )
        result = await self._require_session().execute(
            update(Job)
            .where(Job.id.in_(candidates))
            .values(
                status="cancelled",
                worker_id=None,
                lease_until=None,
                error="MODE_PREPARATION_CANCELLED",
                updated_at=datetime.now(UTC),
            )
            .returning(Job.id)
        )
        return len(list(result.scalars()))
