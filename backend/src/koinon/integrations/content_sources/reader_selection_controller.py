# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Interactive caller-owned source selection; never an account-management token grant."""

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, Valid, get_mapping, put_mapping, request_mapping
from starlette.requests import Request

from koinon.integrations.content_sources.controllers import _actor, _safe, _session
from koinon.integrations.content_sources.read_dtos import ReaderSelectionInput, ReaderSelectionOutput
from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/content-sources")
class SourceReaderSelectionController:
    def __init__(self, selections: SourceReaderSelections):
        self.selections = selections

    @get_mapping("/reader-selection")
    async def get(self, tenant_id: PathVar[str], request: Request) -> ReaderSelectionOutput:
        return await _safe(self.selections.get(_actor(request), tenant_id))

    @put_mapping("/reader-selection")
    async def replace(
        self, tenant_id: PathVar[str], body: Valid[Body[ReaderSelectionInput]], request: Request
    ) -> ReaderSelectionOutput:
        _session(request)
        return await _safe(self.selections.replace(_actor(request), tenant_id, body))
