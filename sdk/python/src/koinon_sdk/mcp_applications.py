# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/mcp_applications/dtos.py
SHA256: 1ca12e63762dfd35683231647b72c67d9e122fc14cf24fc74630c1ba5dabc7a0

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import InputModel

McpOAuthScope = Literal[
    "catalog:read",
    "catalog:write",
    "ingest:write",
    "knowledge:search",
    "query:execute",
    "chat:use",
    "evidence:read",
]


class McpOAuthClientValues(InputModel):
    name: str = Field(min_length=1, max_length=120, strict=True)
    redirect_uris: list[str] = Field(min_length=1, max_length=8)
    scopes: list[McpOAuthScope] = Field(min_length=1, max_length=7)


class McpOAuthClientInput(McpOAuthClientValues):
    client_type: Literal["public", "confidential"]


class McpOAuthClientRevision(InputModel):
    expected_revision: int = Field(ge=1, le=2147483646, strict=True)


class McpOAuthClientPatch(McpOAuthClientRevision):
    name: str | None = Field(default=None, min_length=1, max_length=120, strict=True)
    redirect_uris: list[str] | None = Field(default=None, min_length=1, max_length=8)
    scopes: list[McpOAuthScope] | None = Field(default=None, min_length=1, max_length=7)
    enabled: bool | None = Field(default=None, strict=True)


class McpOAuthClient(McpOAuthClientValues):
    id: str
    tenant_id: str
    client_id: str
    client_type: Literal["public", "confidential"]
    enabled: bool
    revision: int
    created_at: AwareDatetime
    updated_at: AwareDatetime
    created_by: str
    updated_by: str


class McpOAuthClientCredential(InputModel):
    client: McpOAuthClient
    client_secret: str | None = Field(default=None, repr=False)


class McpOAuthClientReadiness(InputModel):
    ready: bool
    endpoint_enabled: bool
    oauth_enabled: bool
    encryption_configured: bool
    missing_configuration: list[Literal["mcp_endpoint", "oauth_enabled", "oauth_encryption_key"]]
    static_clients_read_only: bool = True


class McpOAuthClientPage(InputModel):
    items: list[McpOAuthClient]
    total: int
    page: int
    page_size: int
    pages: int
