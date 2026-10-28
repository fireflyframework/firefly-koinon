# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import (
    get_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.catalog.mappers import entry_dto, member_dto
from koinon.catalog.service import CatalogService
from koinon.security.identity import identity_from_request


@rest_controller
@request_mapping("/api/v1")
class ContextController:
    def __init__(self, catalog: CatalogService):
        self.catalog = catalog

    @get_mapping("/context")
    async def context(self, request: Request) -> dict:
        context = await self.catalog.context(identity_from_request(request).subject)
        return {
            **context,
            "memberships": [member_dto(member) for member in context["memberships"]],
            "workspaces": [entry_dto(entry) for entry in context["workspaces"]],
        }
