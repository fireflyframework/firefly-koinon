# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed read-only activity reports for the authenticated user or current administrators."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, post_mapping, request_mapping
from starlette.requests import Request

from koinon.activity.dtos import ActivitySummary, ActivityWindow
from koinon.activity.ports import ActivitySummaryReader
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class ActivityController:
    def __init__(self, summaries: ActivitySummaryReader):
        self.summaries = summaries

    @post_mapping("/tenants/{tenant_id}/activity/personal")
    async def personal(
        self, tenant_id: PathVar[str], body: Valid[Body[ActivityWindow]], request: Request
    ) -> ActivitySummary:
        return await self.summaries.personal(identity_from_request(request).subject, tenant_id, body)

    @post_mapping("/tenants/{tenant_id}/activity/administration")
    async def administrative(
        self, tenant_id: PathVar[str], body: Valid[Body[ActivityWindow]], request: Request
    ) -> ActivitySummary:
        return await self.summaries.administrative(identity_from_request(request).subject, tenant_id, body)
