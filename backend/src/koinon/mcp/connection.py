# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import service
from pyfly.core import Config
from pyfly.data import transactional

from koinon.catalog.errors import AccessDenied
from koinon.catalog.service import CatalogService
from koinon.mcp.dtos import McpConnectionDescriptor, McpRegisteredClient, McpReviewSupport, McpToolCapability
from koinon.mcp.server import APP_ONLY_TOOLS, REVIEW_TOOLS, TOOL_SCOPES
from koinon.mcp.settings import McpSettings
from koinon.mcp_applications.repositories import McpOAuthClientRepository
from koinon.mcp_auth.settings import MCP_SCOPES, McpOAuthSettings


@service(name="mcp.connection")
class McpConnectionService:
    def __init__(
        self,
        settings: McpSettings,
        config: Config,
        oauth: McpOAuthSettings,
        catalog: CatalogService | None = None,
        registrations: McpOAuthClientRepository | None = None,
    ):
        self.settings, self.config, self.oauth = settings, config, oauth
        self.catalog, self.registrations = catalog, registrations

    @transactional(read_only=True)
    async def organization_descriptor(self, subject: str, tenant_id: str) -> McpConnectionDescriptor:
        if self.catalog is None:
            raise AccessDenied("Organization connection details are unavailable", code="ACCESS_DENIED")
        members = [
            member for member in await self.catalog.memberships(subject) if member.tenant_id == tenant_id
        ]
        allowed = False
        for member in members:
            if "catalog:read" in await self.catalog.permissions(subject, tenant_id, member.workspace_id):
                allowed = True
                break
        if not allowed:
            raise AccessDenied("Organization connection details are unavailable", code="ACCESS_DENIED")
        descriptor = self.descriptor()
        if not descriptor.oauth_enabled or self.registrations is None:
            return descriptor
        rows = await self.registrations.find_all(tenant_id=tenant_id, enabled=True)
        static_ids = {value["client_id"] for value in self.oauth.clients}
        clients = []
        for row in sorted(rows, key=lambda value: (value.name, value.id)):
            if row.client_id in static_ids:
                raise AccessDenied("OAuth client configuration is ambiguous", code="CLIENT_UNAVAILABLE")
            clients.append(
                McpRegisteredClient(
                    client_id=row.client_id,
                    name=row.name,
                    scopes=tuple(row.scopes),
                    client_auth=row.client_type,
                )
            )
        return descriptor.model_copy(update={"clients": (*clients, *descriptor.clients)})

    def descriptor(self) -> McpConnectionDescriptor:
        enabled = self.settings.enabled
        oauth = enabled and self.oauth.enabled
        return McpConnectionDescriptor(
            enabled=enabled,
            local_only=enabled and self.settings.local_only,
            endpoint=self.settings.public_url if enabled else None,
            authentication=("personal_token", "oauth") if oauth else ("personal_token",),
            clients=tuple(
                McpRegisteredClient(
                    client_id=value["client_id"],
                    name=value["name"],
                    scopes=tuple(value["scopes"]),
                    client_auth="confidential" if value.get("client_secret_hash") is not None else "public",
                )
                for value in self.oauth.clients
            )
            if oauth
            else (),
            oauth_enabled=oauth,
            oauth_registration="pre_registered" if oauth else None,
            supported_scopes=tuple(sorted(MCP_SCOPES)),
            tools=tuple(
                McpToolCapability(
                    name=name,
                    required_scopes=scopes,
                    access="app_only"
                    if name in APP_ONLY_TOOLS
                    else "proposal"
                    if name in REVIEW_TOOLS
                    else "query"
                    if name == "koinon_query"
                    else "read",
                    requires_app=name in REVIEW_TOOLS,
                )
                for name, scopes in TOOL_SCOPES.items()
            ),
            review=McpReviewSupport(
                supported=enabled and bool(self.config.get("koinon.knowledge.enabled", True))
            ),
        )
