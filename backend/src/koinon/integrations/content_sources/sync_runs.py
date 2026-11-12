# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Source-run leases use canonical Jobs and never discard unknown native effects."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from pyfly.container import repository
from pyfly.data.relational.sqlalchemy import Repository
from pyfly.kernel import ConflictException
from sqlalchemy import exists, func, select, update

from koinon.integrations.content_sources.entities import PersonalSourceConnection
from koinon.integrations.content_sources.mapping_dtos import MappingReviewInput
from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
from koinon.integrations.content_sources.read_authority import source_authority
from koinon.integrations.content_sources.sync_controls import SyncAuthorityCapture
from koinon.integrations.content_sources.sync_entities import (
    SourceMappingPolicy,
    SourceSyncObservation,
    SourceSyncRun,
    SourceSyncState,
    SourceSyncWork,
)
from koinon.jobs.entities import Job
from koinon.knowledge.bulk.ports import NativeCommit


def lost():
    return ConflictException("Source execution lease is unavailable", code="SOURCE_LEASE_LOST")


@dataclass(frozen=True, slots=True)
class SourceRunLease:
    tenant_id: str
    owner: str
    mapping_id: str
    run_id: str
    job_id: str
    worker_id: str
    attempt: int
    mapping_revision: int
    connection_revision: int
    policy_id: str
    expires_at: datetime
    reconciliation_only: bool


@dataclass(frozen=True, slots=True)
class SourceReplacementExecution:
    run_lease: SourceRunLease
    attempt_id: str
    content_operation_id: str


@dataclass(frozen=True, slots=True)
class SourceReplacementAcknowledgementExecution:
    """Confirm one persisted native receipt without granting producer execution."""

    run_lease: SourceRunLease
    attempt_id: str
    content_operation_id: str
    receipt: NativeCommit


@repository(name="content_sources.runs")
class SourceRunRepository(Repository[SourceSyncRun, str]):
    @staticmethod
    def _observed_work(run_id):
        return exists().where(
            SourceSyncObservation.run_id == run_id, SourceSyncObservation.work_id == SourceSyncWork.id
        )

    async def finish(self, lease: SourceRunLease, *, capture: SyncAuthorityCapture | None = None, at=None):
        """Settle known work and retire only an authoritative complete enumeration.

        One call retires at most100 missing objects; callers repeat the same leased
        run. Unknown native outcomes retain reconciling state and cannot complete.
        Caller owns canonical destination authority and the surrounding transaction.
        """
        from koinon.integrations.content_sources.sync_checkpoints import event_hash

        session = self._require_session()
        now = at or datetime.now(UTC)
        connection, mapping, run = await self.identity(lease.tenant_id, lease.owner, lease.run_id)
        current = await session.scalar(
            select(SourceSyncState)
            .where(SourceSyncState.mapping_id == mapping.id, SourceSyncState.tenant_id == lease.tenant_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        cancelled = run.cancel_requested_at is not None or mapping.status == "retired"
        work_filter = (
            SourceSyncWork.tenant_id == lease.tenant_id,
            SourceSyncWork.mapping_id == mapping.id,
            self._observed_work(run.id),
        )
        await self.fenced(lease, at=now, lock_job=False)
        if cancelled:
            await session.execute(
                update(SourceSyncWork)
                .where(*work_filter, SourceSyncWork.status == "admitted", SourceSyncWork.attempt_id.is_(None))
                .values(status="removed", error_code="SOURCE_CANCELLED", updated_at=now)
            )
        counts = dict(
            (
                await session.execute(
                    select(SourceSyncWork.status, func.count())
                    .where(*work_filter)
                    .group_by(SourceSyncWork.status)
                )
            ).all()
        )
        run.counters_json, run.updated_at = counts, now
        if counts.get("processing", 0):
            run.status = "reconciling"
            await session.flush()
            return False
        if counts.get("admitted", 0):
            await session.flush()
            return False
        if not cancelled:
            if not run.enumeration_complete:
                await session.flush()
                return False
            policy = await session.get(SourceMappingPolicy, run.policy_id)
            if (
                capture is None
                or current is None
                or policy is None
                or policy.accepted_at is None
                or current.accepted_policy_id != policy.id
                or mapping.revision != run.mapping_revision
                or mapping.status not in {"active", "paused"}
                or connection.status != "connected"
                or connection.refresh_operation is not None
                or connection.secret_ciphertext is None
                or connection.revision != capture.connection_revision
                or connection.revision != run.connection_revision
                or policy.authority_sha256 != capture.authority_sha256
                or source_authority(connection)[1] != capture.authority_sha256
                or (capture.policy_id, capture.policy_sha256) != (policy.id, policy.policy_sha256)
            ):
                raise lost()
            unseen = ~exists().where(
                SourceSyncObservation.run_id == run.id, SourceSyncObservation.object_id == SourceObject.id
            )
            missing = list(
                (
                    await session.scalars(
                        select(SourceObject)
                        .where(
                            SourceObject.tenant_id == lease.tenant_id,
                            SourceObject.mapping_id == mapping.id,
                            SourceObject.state.in_(("pending", "imported", "failed")),
                            unseen,
                        )
                        .order_by(SourceObject.id)
                        .limit(101)
                        .with_for_update()
                        .execution_options(populate_existing=True)
                    )
                ).all()
            )
            if missing:
                page = run.page_sequence + 1
                for position, origin in enumerate(missing[:100]):
                    origin.generation += 1
                    origin.state, origin.mapping_revision, origin.updated_at = (
                        "removed",
                        mapping.revision,
                        now,
                    )
                    payload = {
                        "reason": "missing_from_complete_scan",
                        "object_id": origin.id,
                        "generation": origin.generation,
                    }
                    digest, identifier = event_hash(payload), str(uuid4())
                    work = SourceSyncWork(
                        id=identifier,
                        tenant_id=lease.tenant_id,
                        mapping_id=mapping.id,
                        object_id=origin.id,
                        generation=origin.generation,
                        remote_version=None,
                        event_sha256=digest,
                        status="removed",
                        error_code="SOURCE_REMOVED",
                        attempt_id=None,
                        expected_local_revision=origin.published_local_revision,
                        expected_sha256=origin.published_sha256,
                    )
                    session.add(work)
                    await session.flush()
                    session.add(
                        SourceSyncObservation(
                            id=str(uuid4()),
                            tenant_id=lease.tenant_id,
                            mapping_id=mapping.id,
                            run_id=run.id,
                            page_sequence=page,
                            item_sequence=position,
                            object_id=origin.id,
                            generation=origin.generation,
                            remote_version=None,
                            event_json=payload,
                            event_sha256=digest,
                            work_id=identifier,
                        )
                    )
                run.page_sequence = page
                selected = MappingReviewInput.model_validate(policy.policy_json["request"])
                if selected.removal_policy == "pause_for_review":
                    mapping.status, current.enabled, current.next_run_at = "paused", False, None
                    current.revision += 1
                await session.flush()
                counts = dict(
                    (
                        await session.execute(
                            select(SourceSyncWork.status, func.count())
                            .where(*work_filter)
                            .group_by(SourceSyncWork.status)
                        )
                    ).all()
                )
                run.counters_json = counts
                if len(missing) > 100:
                    return False
            current.last_complete_scan_generation = run.scan_generation
            current.cursor_ciphertext = run.cursor_ciphertext
            current.revision += 1
            current.updated_at = now
        # The canonical Job is last in the lock order and settles in the same commit.
        _, run, job = await self.fenced(lease, at=now)
        run.status = (
            "cancelled"
            if cancelled
            else "partial"
            if counts.get("failed", 0) or counts.get("conflict", 0)
            else "succeeded"
        )
        run.finished_at, run.updated_at = now, now
        job.status = "cancelled" if cancelled else "succeeded"
        job.result, job.progress, job.error = {"run_id": run.id, "status": run.status}, 100, None
        job.worker_id, job.lease_until, job.updated_at = None, None, now
        await session.flush()
        return True

    async def identity(self, tenant: str, owner: str, run_id: str):
        """Caller holds canonical destination authority before this lock sequence."""
        session = self._require_session()
        connection = await session.scalar(
            select(PersonalSourceConnection)
            .join(
                SourceMapping,
                SourceMapping.connection_id == PersonalSourceConnection.id,
            )
            .join(SourceSyncRun, SourceSyncRun.mapping_id == SourceMapping.id)
            .where(
                SourceSyncRun.id == run_id,
                SourceSyncRun.tenant_id == tenant,
                SourceMapping.tenant_id == tenant,
                SourceMapping.owner == owner,
                PersonalSourceConnection.tenant_id == tenant,
                PersonalSourceConnection.owner == owner,
            )
            .with_for_update(of=PersonalSourceConnection)
            .execution_options(populate_existing=True)
        )
        if connection is None:
            raise lost()
        mapping = await session.scalar(
            select(SourceMapping)
            .join(
                SourceSyncRun,
                SourceSyncRun.mapping_id == SourceMapping.id,
            )
            .where(
                SourceSyncRun.id == run_id, SourceMapping.tenant_id == tenant, SourceMapping.owner == owner
            )
            .with_for_update(of=SourceMapping)
            .execution_options(populate_existing=True)
        )
        run = await session.scalar(
            select(SourceSyncRun)
            .where(
                SourceSyncRun.id == run_id,
                SourceSyncRun.tenant_id == tenant,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if mapping is None or run is None or run.mapping_id != mapping.id:
            raise lost()
        return connection, mapping, run

    async def _job(self, run, *, lock=True):
        statement = select(Job)
        statement = statement.where(
            Job.id == run.job_id,
            Job.tenant_id == run.tenant_id,
            Job.resource_id == run.mapping_id,
            Job.kind == "content.source.reconcile",
        ).execution_options(populate_existing=True)
        if lock:
            statement = statement.with_for_update()
        job = await self._require_session().scalar(statement)
        if job is None:
            raise lost()
        return job

    async def claim(self, tenant, owner, run_id, worker, *, at=None, lease_seconds=120):
        if not isinstance(worker, str) or not 1 <= len(worker) <= 64 or not 30 <= lease_seconds <= 3600:
            raise ValueError("Use bounded source worker and lease")
        now = at or datetime.now(UTC)
        connection, mapping, run = await self.identity(tenant, owner, run_id)
        if run.status not in {"queued", "running", "reconciling"}:
            return None
        job = await self._job(run)
        if (
            job.available_at > now
            or job.attempts >= job.max_attempts
            or job.status not in {"queued", "running"}
            or job.status == "running"
            and job.lease_until is not None
            and job.lease_until > now
        ):
            return None
        recovery = job.attempts > 0 or job.status == "running" or run.status == "reconciling"
        inspection_only = (
            run.cancel_requested_at is not None
            or mapping.status not in {"active", "paused"}
            or mapping.revision != run.mapping_revision
            or connection.status != "connected"
            or connection.revision != run.connection_revision
            or connection.refresh_operation is not None
        )
        job.status, job.worker_id, job.lease_until = "running", worker, now + timedelta(seconds=lease_seconds)
        job.attempts += 1
        job.updated_at = run.updated_at = now
        run.status = "reconciling" if recovery or inspection_only else "running"
        await self._require_session().flush()
        return SourceRunLease(
            tenant,
            owner,
            mapping.id,
            run.id,
            job.id,
            worker,
            job.attempts,
            run.mapping_revision,
            run.connection_revision,
            run.policy_id,
            job.lease_until,
            inspection_only,
        )

    async def fenced(self, lease: SourceRunLease, *, at=None, publication=False, lock_job=True):
        now = at or datetime.now(UTC)
        connection, mapping, run = await self.identity(lease.tenant_id, lease.owner, lease.run_id)
        job = await self._job(run, lock=lock_job)
        if (
            (run.mapping_id, run.job_id, run.mapping_revision, run.connection_revision, run.policy_id)
            != (
                lease.mapping_id,
                lease.job_id,
                lease.mapping_revision,
                lease.connection_revision,
                lease.policy_id,
            )
            or run.status not in {"running", "reconciling"}
            or job.status != "running"
            or job.worker_id != lease.worker_id
            or job.attempts != lease.attempt
            or job.lease_until is None
            or job.lease_until <= now
        ):
            raise lost()
        if publication and (
            lease.reconciliation_only
            or run.cancel_requested_at is not None
            or mapping.status not in {"active", "paused"}
            or mapping.revision != run.mapping_revision
            or connection.status != "connected"
            or connection.revision != run.connection_revision
            or connection.refresh_operation is not None
            or connection.secret_ciphertext is None
        ):
            raise lost()
        return mapping, run, job

    async def renew(self, lease: SourceRunLease, *, at=None, lease_seconds=120):
        if not 30 <= lease_seconds <= 3600:
            raise ValueError("Use a bounded lease")
        now = at or datetime.now(UTC)
        _, run, job = await self.fenced(lease, at=now)
        job.lease_until = now + timedelta(seconds=lease_seconds)
        job.updated_at = run.updated_at = now
        await self._require_session().flush()

    async def renew_owned(self, lease: SourceRunLease, *, lease_seconds: int) -> SourceRunLease | None:
        """Renew exact live ownership, without touching attempts or scheduler ordering."""
        if type(lease_seconds) is not int or not 300 <= lease_seconds <= 3600:
            raise ValueError("Use a bounded source heartbeat lease")
        session = self._require_session()
        # Closed scalar projections preserve lock order without hydrating retained content.
        connection = await session.scalar(
            select(PersonalSourceConnection.id)
            .join(SourceMapping, SourceMapping.connection_id == PersonalSourceConnection.id)
            .where(
                SourceMapping.id == lease.mapping_id,
                SourceMapping.tenant_id == lease.tenant_id,
                SourceMapping.owner == lease.owner,
                PersonalSourceConnection.tenant_id == lease.tenant_id,
                PersonalSourceConnection.owner == lease.owner,
                PersonalSourceConnection.status == "connected",
                PersonalSourceConnection.revision == lease.connection_revision,
                PersonalSourceConnection.refresh_operation.is_(None),
                PersonalSourceConnection.secret_ciphertext.is_not(None),
            )
            .with_for_update(of=PersonalSourceConnection)
        )
        if connection is None or lease.reconciliation_only:
            return None
        mapping = await session.scalar(
            select(SourceMapping.id)
            .where(
                SourceMapping.id == lease.mapping_id,
                SourceMapping.tenant_id == lease.tenant_id,
                SourceMapping.owner == lease.owner,
                SourceMapping.connection_id == connection,
                SourceMapping.revision == lease.mapping_revision,
                SourceMapping.status.in_(("active", "paused")),
            )
            .with_for_update()
        )
        if mapping is None:
            return None
        run = await session.scalar(
            select(SourceSyncRun.id)
            .where(
                SourceSyncRun.id == lease.run_id,
                SourceSyncRun.tenant_id == lease.tenant_id,
                SourceSyncRun.mapping_id == lease.mapping_id,
                SourceSyncRun.job_id == lease.job_id,
                SourceSyncRun.mapping_revision == lease.mapping_revision,
                SourceSyncRun.connection_revision == lease.connection_revision,
                SourceSyncRun.policy_id == lease.policy_id,
                SourceSyncRun.status.in_(("running", "reconciling")),
                SourceSyncRun.cancel_requested_at.is_(None),
                exists().where(
                    SourceSyncState.mapping_id == lease.mapping_id,
                    SourceSyncState.tenant_id == lease.tenant_id,
                    SourceSyncState.accepted_policy_id == lease.policy_id,
                ),
                exists().where(
                    SourceMappingPolicy.id == lease.policy_id,
                    SourceMappingPolicy.tenant_id == lease.tenant_id,
                    SourceMappingPolicy.mapping_id == lease.mapping_id,
                    SourceMappingPolicy.owner == lease.owner,
                    SourceMappingPolicy.accepted_at.is_not(None),
                ),
            )
            .with_for_update()
        )
        if run is None:
            return None
        job = (
            await session.execute(
                select(Job.worker_id, Job.attempts, Job.lease_until)
                .where(
                    Job.id == lease.job_id,
                    Job.tenant_id == lease.tenant_id,
                    Job.resource_id == lease.mapping_id,
                    Job.kind == "content.source.reconcile",
                    Job.status == "running",
                )
                .with_for_update()
            )
        ).first()
        now = await session.scalar(select(func.clock_timestamp()))
        if now is None:
            raise lost()
        if (
            job is None
            or job.worker_id != lease.worker_id
            or job.attempts != lease.attempt
            or job.lease_until is None
            or job.lease_until <= now
        ):
            return None
        expiry = now + timedelta(seconds=lease_seconds)
        await session.execute(update(Job).where(Job.id == lease.job_id).values(lease_until=expiry))
        return replace(lease, expires_at=expiry)
