# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Authorize management operations before touching the durable worker queue."""

from pyfly.container import service
from pyfly.data import transactional

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.jobs.mappers import job_dto
from koinon.jobs.service import JobService


@service(name="jobs.management")
class JobManagementService:
    def __init__(self, catalog: CatalogService, jobs: JobService):
        self.catalog, self.jobs = catalog, jobs

    async def list(self, subject: str, tenant_id: str) -> dict:
        await self.catalog.list(subject, tenant_id, kind="workspace")
        visible = []
        for job in await self.jobs.repository.find_all(tenant_id=tenant_id):
            try:
                await self.catalog.get(subject, tenant_id, job.resource_id)
            except AccessDenied:
                continue
            visible.append(job_dto(job))
        return {"items": visible}

    @transactional(read_only=True)
    async def get(self, subject: str, tenant_id: str, job_id: str) -> dict:
        rows = await self.jobs.repository.find_all(id=job_id, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("Job is not accessible in this context", code="ACCESS_DENIED")
        await self.catalog.get(subject, tenant_id, rows[0].resource_id)
        return job_dto(rows[0])

    @transactional
    async def cancel(self, subject: str, tenant_id: str, job_id: str) -> dict:
        rows = await self.jobs.repository.find_all(id=job_id, tenant_id=tenant_id)
        if not rows:
            raise AccessDenied("Job is not accessible in this context", code="ACCESS_DENIED")
        resource = await self.catalog.get(subject, tenant_id, rows[0].resource_id)
        permissions = await self.catalog.permissions(subject, tenant_id, resource.workspace_id)
        permission = "jobs:manage" if "jobs:manage" in permissions else "ingest:write"
        await self.catalog.authorize(subject, tenant_id, permission, resource.workspace_id)
        job = await self.jobs.cancel(tenant_id, job_id)
        await self.catalog._audit(subject, tenant_id, "job.cancelled", job_id)
        return job_dto(job)
