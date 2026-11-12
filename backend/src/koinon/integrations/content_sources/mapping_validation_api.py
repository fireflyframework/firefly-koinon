# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Interactive-browser preparation. None of these routes approves or starts an import."""

from uuid import UUID

from pyfly.container import rest_controller
from pyfly.web import Body, PathVar, QueryParam, Valid, get_mapping, post_mapping, request_mapping
from starlette.requests import Request

from koinon.integrations.content_sources.controllers import _actor, _safe, _session
from koinon.integrations.content_sources.mapping_validation import SourceMappingValidations
from koinon.integrations.content_sources.mapping_validation_dtos import (
    SourceMappingValidationAbandonInput,
    SourceMappingValidationContinueInput,
    SourceMappingValidationInput,
    SourceMappingValidationItemPage,
    SourceMappingValidationOutput,
)


@rest_controller
@request_mapping("/api/v1/tenants/{tenant_id}/content-sources")
class SourceMappingValidationController:
    def __init__(self, validations: SourceMappingValidations):
        self.validations = validations

    @post_mapping("/mapping-validations", status_code=201)
    async def begin(
        self, tenant_id: PathVar[str], body: Valid[Body[SourceMappingValidationInput]], request: Request
    ) -> SourceMappingValidationOutput:
        return await _safe(
            self.validations.begin_validation(_actor(request), tenant_id, _session(request), body)
        )

    @get_mapping("/mapping-validations/operations/{operation_id}")
    async def receipt(
        self, tenant_id: PathVar[str], operation_id: PathVar[UUID], request: Request
    ) -> SourceMappingValidationOutput:
        return await _safe(
            self.validations.creation_receipt(_actor(request), tenant_id, _session(request), operation_id)
        )

    @get_mapping("/mapping-validations/{validation_id}")
    async def status(
        self, tenant_id: PathVar[str], validation_id: PathVar[UUID], request: Request
    ) -> SourceMappingValidationOutput:
        return await _safe(
            self.validations.validation_status(_actor(request), tenant_id, _session(request), validation_id)
        )

    @post_mapping("/mapping-validations/{validation_id}/continue")
    async def advance(
        self,
        tenant_id: PathVar[str],
        validation_id: PathVar[UUID],
        body: Valid[Body[SourceMappingValidationContinueInput]],
        request: Request,
    ) -> SourceMappingValidationOutput:
        return await _safe(
            self.validations.continue_validation(
                _actor(request), tenant_id, _session(request), validation_id, body
            )
        )

    @get_mapping("/mapping-validations/{validation_id}/items")
    async def items(
        self,
        tenant_id: PathVar[str],
        validation_id: PathVar[UUID],
        request: Request,
        cursor: QueryParam[str | None] = None,
        limit: QueryParam[int] = 25,
    ) -> SourceMappingValidationItemPage:
        return await _safe(
            self.validations.validation_items(
                _actor(request), tenant_id, _session(request), validation_id, limit=limit, cursor=cursor
            )
        )

    @post_mapping("/mapping-validations/{validation_id}/abandon")
    async def abandon(
        self,
        tenant_id: PathVar[str],
        validation_id: PathVar[UUID],
        body: Valid[Body[SourceMappingValidationAbandonInput]],
        request: Request,
    ) -> SourceMappingValidationOutput:
        return await _safe(
            self.validations.abandon_validation(
                _actor(request), tenant_id, _session(request), validation_id, body.expected_revision
            )
        )
