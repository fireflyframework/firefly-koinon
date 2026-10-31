# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Counts-only, bounded operational observations; never a public resource grant."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal

import sqlalchemy as sa
from pyfly.container import Container, service
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import Isolation, Propagation, TransactionTemplate

from koinon.assistants.entities import ChatRun
from koinon.corporate_identity.entities import CorporateProvider
from koinon.corporate_profiles.entities import CorporateProfileSnapshot
from koinon.jobs.entities import Job
from koinon.knowledge.indexes.entities import KnowledgeIndex
from koinon.operations.settings import OperationalSettings
from koinon.organization_people.entities import OrganizationProfileMappingRecord
from koinon.workers.admission import WorkAdmissionSettings

QueueName = Literal[
    "conversation", "index", "attachment", "profile", "document_ingest", "structured_ingest", "callback"
]
_MAX_ROWS = 100000


@dataclass(frozen=True, slots=True)
class QueueObservation:
    queue: QueueName
    ready: int | None
    active: int | None
    retry: int | None
    oldest_ready_age_seconds: float | None
    capacity: int
    capped: bool = False
    available: bool = True

    @property
    def demand(self) -> int | None:
        if not self.available:
            return None
        assert self.ready is not None and self.active is not None
        return self.ready + self.active


@dataclass(frozen=True, slots=True)
class WorkerObservation:
    observed_at: datetime
    queues: tuple[QueueObservation, ...]
    process_capacity: int


def queue_statement(source, ready, active, retry, created, *, limit):
    eligible = sa.select(
        sa.case((ready, 1), else_=0).label("ready"),
        sa.case((active, 1), else_=0).label("active"),
        sa.case((sa.and_(ready, retry), 1), else_=0).label("retry"),
        sa.case((ready, created), else_=None).label("oldest"),
    ).select_from(source)
    eligible = eligible.where(sa.or_(ready, active)).order_by(created).limit(limit + 1).subquery()
    return sa.select(
        sa.func.count().label("total"),
        sa.func.sum(eligible.c.ready).label("ready"),
        sa.func.sum(eligible.c.active).label("active"),
        sa.func.sum(eligible.c.retry).label("retry"),
        sa.func.min(eligible.c.oldest).label("oldest"),
    )


async def measure_queue(
    datasource,
    queue: QueueName,
    source,
    ready,
    active,
    retry,
    created,
    *,
    capacity: int,
    limit: int = _MAX_ROWS,
) -> QueueObservation:
    if (
        type(limit) is not int
        or not 1 <= limit <= _MAX_ROWS
        or type(capacity) is not int
        or not 1 <= capacity <= 100
    ):
        raise ValueError("Use a bounded queue observation and capacity")
    async with TransactionTemplate(
        datasource,
        propagation=Propagation.REQUIRES_NEW,
        isolation=Isolation.SERIALIZABLE,
        read_only=True,
        read_from_primary=True,
    ).transaction() as unit:
        assert unit is not None
        row = (
            (await unit.resource.execute(queue_statement(source, ready, active, retry, created, limit=limit)))
            .mappings()
            .one()
        )
    count = int(row["total"])
    capped = count > limit
    ready_count = min(limit, int(row["ready"] or 0))
    active_count = min(limit - ready_count, int(row["active"] or 0))
    oldest = row["oldest"]
    if isinstance(oldest, str):
        oldest = datetime.fromisoformat(oldest)
    if oldest is not None and oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=UTC)
    age = max(0, (datetime.now(UTC) - oldest).total_seconds()) if oldest is not None else None
    return QueueObservation(
        queue, ready_count, active_count, min(ready_count, int(row["retry"] or 0)), age, capacity, capped
    )


@service(name="operations.worker_backlog")
class WorkerBacklog:
    def __init__(
        self,
        datasources: DataSourceRegistry,
        settings: OperationalSettings,
        container: Container,
        admission: WorkAdmissionSettings,
    ):
        self.datasources, self.settings, self.container = datasources, settings, container
        self.admission = admission

    async def snapshot(self, *, limit: int = _MAX_ROWS) -> WorkerObservation:
        now = datetime.now(UTC)
        rows = []

        async def observe(name, source, table, ready, active, retry, created, capacity):
            capacity = min(capacity, self.admission.worker_capacity)
            if source not in self.datasources.names():
                rows.append(QueueObservation(name, None, None, None, None, capacity, available=False))
                return
            rows.append(
                await measure_queue(
                    self.datasources.get(source),
                    name,
                    table,
                    ready,
                    active,
                    retry,
                    created,
                    capacity=capacity,
                    limit=limit,
                )
            )

        ready = sa.or_(
            sa.and_(ChatRun.status == "queued", ChatRun.available_at <= now),
            sa.and_(ChatRun.status == "running", ChatRun.lease_until <= now),
        )
        active = sa.and_(ChatRun.status == "running", ChatRun.lease_until > now)
        await observe(
            "conversation",
            "primary",
            ChatRun,
            sa.and_(ready, ChatRun.attempts < 2),
            active,
            ChatRun.attempts > 0,
            ChatRun.created_at,
            self.settings.worker_concurrency,
        )
        ready = sa.and_(
            sa.or_(
                sa.and_(Job.status == "queued", Job.available_at <= now),
                sa.and_(Job.status == "running", Job.lease_until <= now),
            ),
            Job.attempts < Job.max_attempts,
        )
        active = sa.and_(Job.status == "running", Job.lease_until > now)
        indexes = Job.__table__.join(KnowledgeIndex, KnowledgeIndex.job_id == Job.id)
        relevant = sa.and_(
            Job.kind == "knowledge.index", KnowledgeIndex.status.in_(("queued", "building", "awaiting_index"))
        )
        await observe(
            "index",
            "primary",
            indexes,
            sa.and_(ready, relevant),
            sa.and_(active, relevant),
            Job.attempts > 0,
            Job.created_at,
            1,
        )
        relevant = Job.kind.in_(
            ("chat.attachment.extract", "chat.attachment.expire", "chat.attachment.purge")
        )
        await observe(
            "attachment",
            "primary",
            Job,
            sa.and_(ready, relevant),
            sa.and_(active, relevant),
            Job.attempts > 0,
            Job.created_at,
            1,
        )
        profile = CorporateProfileSnapshot
        mapping = OrganizationProfileMappingRecord
        # EXISTS avoids counting one profile twice when it has several enabled mappings.
        policy = sa.exists(
            sa.select(mapping.tenant_id).where(
                mapping.tenant_id == profile.tenant_id,
                mapping.provider_id == profile.provider_id,
                mapping.enabled.is_(True),
                mapping.profile_sync_json.is_not(None),
            )
        )
        provider = sa.exists(
            sa.select(CorporateProvider.id).where(
                CorporateProvider.id == profile.provider_id,
                CorporateProvider.tenant_id == profile.tenant_id,
                CorporateProvider.status == "active",
            )
        )
        base = sa.and_(provider, policy, profile.external_subject.is_not(None), profile.status != "conflict")
        ready = sa.and_(
            base,
            profile.next_due_at <= now,
            sa.or_(profile.lease_until.is_(None), profile.lease_until <= now),
        )
        active = sa.and_(base, profile.status == "running", profile.lease_until > now)
        await observe(
            "profile", "primary", profile, ready, active, profile.lease_generation > 0, profile.next_due_at, 2
        )
        from flycanon.config import CanonSettings
        from flycanon.models.entities.ingest_job import IngestJobRow
        from flyquery.config import FlyquerySettings

        canon = self.container.resolve(CanonSettings) if self.container.contains_type(CanonSettings) else None
        structured = (
            self.container.resolve(FlyquerySettings)
            if self.container.contains_type(FlyquerySettings)
            else None
        )
        doc = IngestJobRow
        cutoff = now - timedelta(seconds=canon.ingest_timeout_s if canon else 600)
        valid = sa.and_(doc.kind == "ingest", doc.attempts <= (canon.ingest_max_attempts if canon else 3))
        ready = sa.and_(
            valid, sa.or_(doc.status == "queued", sa.and_(doc.status == "running", doc.started_at <= cutoff))
        )
        active = sa.and_(doc.kind == "ingest", doc.status == "running", doc.started_at > cutoff)
        await observe(
            "document_ingest", "canon_admin", doc, ready, active, doc.attempts > 0, doc.created_at, 1
        )
        jobs = sa.table(
            "flyquery_ingest_jobs",
            sa.column("status", sa.String),
            sa.column("attempts", sa.Integer),
            sa.column("started_at", sa.DateTime(timezone=True)),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        cutoff = now - timedelta(seconds=structured.processing_lease_s if structured else 1800)
        ready = sa.and_(
            jobs.c.attempts < (structured.ingest_max_attempts if structured else 3),
            sa.or_(
                jobs.c.status == "PENDING", sa.and_(jobs.c.status == "RUNNING", jobs.c.started_at <= cutoff)
            ),
        )
        active = sa.and_(jobs.c.status == "RUNNING", jobs.c.started_at > cutoff)
        await observe(
            "structured_ingest",
            "structured_admin",
            jobs,
            ready,
            active,
            jobs.c.attempts > 0,
            jobs.c.created_at,
            1,
        )
        from flyquery.core.services.callbacks.callback_repository import _OUTBOX

        callback = _OUTBOX.c
        ready = sa.and_(callback.status == "PENDING", callback.next_attempt_at <= now)
        active = sa.and_(
            callback.status == "PENDING",
            callback.next_attempt_at > now,
            callback.last_attempt_at.is_not(None),
            callback.last_status_code.is_(None),
            callback.last_error.is_(None),
        )
        await observe(
            "callback",
            "structured_admin",
            _OUTBOX,
            ready,
            active,
            callback.attempts > 0,
            callback.created_at,
            1,
        )
        return WorkerObservation(now, tuple(rows), self.admission.worker_capacity)
