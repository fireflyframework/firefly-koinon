# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generic workers cannot consume or mutate source-owned execution identities."""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import load
from test_source_migration_postgres import source_database as source_database

from koinon.jobs.entities import Job
from koinon.jobs.errors import JobConflict
from koinon.jobs.repository import JobRepository
from koinon.jobs.service import JobService

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def job_privileges(source_sessions, source_database):
    _, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        load("deploy/provision_roles.py").grant_table(connection, "lattice_jobs", role)


async def test_generic_claim_leaves_queued_and_expired_source_jobs_untouched(source_sessions):
    sessions, _ = source_sessions
    async with sessions.begin() as session:
        for identifier, status in (
            ("source-queued", "queued"),
            ("source-expired", "running"),
            ("ordinary", "queued"),
        ):
            session.add(
                Job(
                    id=identifier,
                    tenant_id="retained",
                    resource_id="folder",
                    kind="ordinary" if identifier == "ordinary" else "content.source.reconcile",
                    payload={},
                    payload_hash="a" * 64,
                    idempotency_key=identifier,
                    status=status,
                    attempts=3 if status == "running" else 0,
                    worker_id="source-worker" if status == "running" else None,
                    lease_until=datetime.now(UTC) - timedelta(seconds=1) if status == "running" else None,
                )
            )
    async with sessions.begin() as session:
        claimed = await JobRepository(session=session).claim("generic-worker", 30)
        assert claimed is not None and claimed.id == "ordinary"
    async with sessions() as session:
        assert (await session.get(Job, "source-queued")).status == "queued"
        expired = await session.get(Job, "source-expired")
        assert (expired.status, expired.worker_id, expired.attempts) == ("running", "source-worker", 3)


async def test_generic_mutation_fence_rejects_source_job_even_with_live_worker_identity(source_sessions):
    sessions, _ = source_sessions
    async with sessions.begin() as session:
        session.add(
            Job(
                id="protected",
                tenant_id="retained",
                resource_id="folder",
                kind="content.source.reconcile",
                payload={},
                payload_hash="a" * 64,
                idempotency_key="protected",
                status="running",
                worker_id="owner",
                lease_until=datetime.now(UTC) + timedelta(minutes=1),
            )
        )
    async with sessions.begin() as session:
        service = JobService(JobRepository(session=session))
        with pytest.raises(JobConflict, match="source"):
            await service._locked("retained", "protected", "owner")
        with pytest.raises(JobConflict, match="source"):
            await service._locked("retained", "protected")
    async with sessions() as session:
        job = await session.get(Job, "protected")
        assert (job.status, job.worker_id) == ("running", "owner")
