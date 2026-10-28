# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0


from pyfly.container import rest_controller
from pyfly.web import (
    Body,
    PathVar,
    Valid,
    get_mapping,
    post_mapping,
    put_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.assistants.configuration_service import AssistantConfigurationService
from koinon.assistants.dtos import ProviderInput
from koinon.operations.service import OperationsService
from koinon.security.identity import identity_from_request


@rest_controller(name="assistants.provider-controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class ProviderController:
    def __init__(self, assistants: AssistantConfigurationService, operations: OperationsService):
        self.assistants = assistants
        self.operations = operations

    @get_mapping("/configuration")
    async def configuration(self, tenant_id: PathVar[str], request: Request) -> dict:
        subject = identity_from_request(request).subject
        return {
            **await self.assistants.configuration(subject, tenant_id),
            "deployment": await self.operations.describe(subject, tenant_id),
        }

    @post_mapping("/providers", status_code=201)
    async def provider_create(
        self, tenant_id: PathVar[str], body: Valid[Body[ProviderInput]], request: Request
    ) -> dict:
        return await self.assistants.save_provider(
            identity_from_request(request).subject,
            tenant_id,
            body.model_dump(exclude_unset=True, exclude_none=True),
        )

    @put_mapping("/providers/{provider_id}")
    async def provider_update(
        self,
        tenant_id: PathVar[str],
        provider_id: PathVar[str],
        body: Valid[Body[ProviderInput]],
        request: Request,
    ) -> dict:
        values = body.model_dump(exclude_unset=True, exclude_none=True)
        if "secret" in body.model_fields_set and body.secret is None:
            values["secret"] = None
        return await self.assistants.save_provider(
            identity_from_request(request).subject,
            tenant_id,
            values,
            provider_id,
        )

    @post_mapping("/providers/{provider_id}/validate")
    async def provider_validate(
        self, tenant_id: PathVar[str], provider_id: PathVar[str], request: Request
    ) -> dict:
        return await self.assistants.validate_provider(
            identity_from_request(request).subject, tenant_id, provider_id
        )
