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
        expired = and_(Job.status == "running", Job.lease_until < now)
        await session.execute(
            update(Job)
            .where(expired, Job.attempts >= Job.max_attempts)
            .values(status="failed", error="Worker lease expired after final attempt", updated_at=now)
        )
        candidate = await session.scalar(
            select(Job)
            .where(
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
