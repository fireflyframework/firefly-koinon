# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import rest_controller
from pyfly.web import get_mapping, request_mapping
from starlette.requests import Request

from koinon.mcp.connection import McpConnectionService
from koinon.mcp.dtos import McpConnectionDescriptor
from koinon.security.identity import identity_from_request


@rest_controller(name="mcp.connection-controller")
@request_mapping("/api/v1/mcp")
class McpConnectionController:
    def __init__(self, connection: McpConnectionService):
        self.connection = connection

    @get_mapping("/connection")
    async def get(self, request: Request) -> McpConnectionDescriptor:
        identity_from_request(request)
        return self.connection.descriptor()
