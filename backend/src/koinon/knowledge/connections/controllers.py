# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import (
    Body,
    PathVar,
    QueryParam,
    Valid,
    delete_mapping,
    get_mapping,
    post_mapping,
    put_mapping,
    request_mapping,
)
from starlette.requests import Request

from koinon.knowledge.connections.dtos import ConnectionInput
from koinon.knowledge.connections.service import KnowledgeConnectionService
from koinon.security.identity import identity_from_request


@rest_controller(name="knowledge.connections_controller")
@request_mapping("/api/v1/tenants/{tenant_id}")
class KnowledgeConnectionsController:
    def __init__(self, connections: KnowledgeConnectionService):
        self.connections = connections

    @get_mapping("/knowledge-roles")
    async def roles(
        self, tenant_id: PathVar[str], request: Request, workspace_id: QueryParam[str | None] = None
    ) -> dict:
        return await self.connections.descriptors(
            identity_from_request(request).subject, tenant_id, workspace_id
        )

    @get_mapping("/knowledge-connections")
    async def list_connections(
        self, tenant_id: PathVar[str], request: Request, workspace_id: QueryParam[str | None] = None
    ) -> dict:
        return {
            "items": await self.connections.list(
                identity_from_request(request).subject, tenant_id, workspace_id
            )
        }

    @post_mapping("/knowledge-connections", status_code=201)
    async def create(
        self, tenant_id: PathVar[str], body: Valid[Body[ConnectionInput]], request: Request
    ) -> dict:
        return await self.connections.save(
            identity_from_request(request).subject, tenant_id, body.model_dump(exclude_unset=True)
        )

    @put_mapping("/knowledge-connections/{connection_id}")
    async def update(
        self,
        tenant_id: PathVar[str],
        connection_id: PathVar[str],
        body: Valid[Body[ConnectionInput]],
        request: Request,
    ) -> dict:
        return await self.connections.save(
            identity_from_request(request).subject,
            tenant_id,
            body.model_dump(exclude_unset=True),
            connection_id,
        )

    @get_mapping("/knowledge-connections/{connection_id}")
    async def get(self, tenant_id: PathVar[str], connection_id: PathVar[str], request: Request) -> dict:
        return await self.connections.get(identity_from_request(request).subject, tenant_id, connection_id)

    @delete_mapping("/knowledge-connections/{connection_id}")
    async def delete(
        self,
        tenant_id: PathVar[str],
        connection_id: PathVar[str],
        request: Request,
        expected_revision: QueryParam[int],
    ) -> dict:
        await self.connections.delete(
            identity_from_request(request).subject,
            tenant_id,
            connection_id,
            expected_revision=expected_revision,
        )
        return {"deleted": True}
