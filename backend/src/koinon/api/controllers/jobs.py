# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import PathVar, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.jobs.management import JobManagementService
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class JobController:
    def __init__(self, jobs: JobManagementService):
        self.jobs = jobs

    @get_mapping("/tenants/{tenant_id}/jobs")
    async def list(self, tenant_id: PathVar[str], request: Request) -> dict:
        return await self.jobs.list(identity_from_request(request).subject, tenant_id)

    @get_mapping("/tenants/{tenant_id}/jobs/{job_id}")
    async def get(self, tenant_id: PathVar[str], job_id: PathVar[str], request: Request) -> dict:
        return await self.jobs.get(identity_from_request(request).subject, tenant_id, job_id)

    @post_mapping("/tenants/{tenant_id}/jobs/{job_id}/cancel")
    async def cancel(self, tenant_id: PathVar[str], job_id: PathVar[str], request: Request) -> dict:
        return await self.jobs.cancel(identity_from_request(request).subject, tenant_id, job_id)
