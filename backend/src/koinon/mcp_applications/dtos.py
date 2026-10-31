# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal
from urllib.parse import urlsplit

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from koinon.mcp_auth.settings import MCP_SCOPES
from koinon.security.settings import _endpoint
from koinon.tokens.service import DEPENDENCIES

McpOAuthScope = Literal[
    "catalog:read",
    "catalog:write",
    "ingest:write",
    "knowledge:search",
    "query:execute",
    "chat:use",
    "evidence:read",
]


class McpOAuthClientValues(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120, strict=True)
    redirect_uris: list[str] = Field(min_length=1, max_length=8)
    scopes: list[McpOAuthScope] = Field(min_length=1, max_length=7)

    @field_validator("name")
    @classmethod
    def printable_name(cls, value):
        if not value.isprintable() or not value.strip():
            raise ValueError("Use a readable application name")
        return value

    @field_validator("redirect_uris")
    @classmethod
    def exact_callbacks(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Use distinct exact callback URLs")
        for value in values:
            if (
                len(value) > 2048
                or any(ord(c) <= 32 or ord(c) >= 127 for c in value)
                or "*" in value
                or "\\" in value
            ):
                raise ValueError("Use exact callback URLs without wildcards")
            _endpoint(value)
            parsed = urlsplit(value)
            if parsed.fragment or parsed.username or parsed.password:
                raise ValueError("Callbacks cannot contain credentials or fragments")
        return values

    @field_validator("scopes")
    @classmethod
    def knowledge_scopes(cls, values):
        selected = set(values)
        if (
            len(selected) != len(values)
            or "catalog:read" not in selected
            or not selected <= MCP_SCOPES
            or any(not DEPENDENCIES.get(scope, set()) <= selected for scope in selected)
        ):
            raise ValueError("Use supported knowledge scopes with their read dependencies")
        return sorted(values)


class McpOAuthClientInput(McpOAuthClientValues):
    client_type: Literal["public", "confidential"]


class McpOAuthClientRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
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


class McpOAuthClientCredential(BaseModel):
    model_config = ConfigDict(extra="forbid")
    client: McpOAuthClient
    client_secret: str | None = Field(default=None, repr=False)


class McpOAuthClientReadiness(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ready: bool
    endpoint_enabled: bool
    oauth_enabled: bool
    encryption_configured: bool
    missing_configuration: list[Literal["mcp_endpoint", "oauth_enabled", "oauth_encryption_key"]]
    static_clients_read_only: bool = True


class McpOAuthClientPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    items: list[McpOAuthClient]
    total: int
    page: int
    page_size: int
    pages: int
