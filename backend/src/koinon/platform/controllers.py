# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Passive organization-wide operational details are separate from public infrastructure probes."""

from pyfly.container import rest_controller
from pyfly.web import PathVar, get_mapping, request_mapping
from starlette.requests import Request

from koinon.platform.dtos import PlatformHealth, SystemInformation
from koinon.platform.ports import PlatformReader
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class PlatformController:
    def __init__(self, reader: PlatformReader):
        self.reader = reader

    @get_mapping("/tenants/{tenant_id}/platform/health")
    async def health(self, tenant_id: PathVar[str], request: Request) -> PlatformHealth:
        return await self.reader.health(identity_from_request(request).subject, tenant_id)

    @get_mapping("/tenants/{tenant_id}/platform/system-information")
    async def system_information(self, tenant_id: PathVar[str], request: Request) -> SystemInformation:
        return await self.reader.system_information(identity_from_request(request).subject, tenant_id)
