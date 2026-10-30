# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pyfly.container import service
from pyfly.core import Config

from koinon.mcp.dtos import McpConnectionDescriptor, McpRegisteredClient, McpReviewSupport, McpToolCapability
from koinon.mcp.server import APP_ONLY_TOOLS, REVIEW_TOOLS, TOOL_SCOPES
from koinon.mcp.settings import McpSettings
from koinon.mcp_auth.settings import MCP_SCOPES, McpOAuthSettings


@service(name="mcp.connection")
class McpConnectionService:
    def __init__(self, settings: McpSettings, config: Config, oauth: McpOAuthSettings):
        self.settings, self.config, self.oauth = settings, config, oauth

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
