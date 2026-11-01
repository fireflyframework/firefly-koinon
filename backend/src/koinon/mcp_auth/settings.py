# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import re
from dataclasses import dataclass, field

from cryptography.fernet import Fernet
from pyfly.container import component
from pyfly.core import config_properties

from koinon.security.settings import _endpoint

MCP_SCOPES = frozenset(
    {
        "catalog:read",
        "catalog:write",
        "ingest:write",
        "knowledge:search",
        "query:execute",
        "chat:use",
        "evidence:read",
        "activity:read",
    }
)


MCP_RESOURCE_SCOPES = MCP_SCOPES | {"audit:read"}


@component(name="mcp.oauth.settings")
@config_properties(prefix="koinon.mcp.oauth")
@dataclass
class McpOAuthSettings:
    enabled: bool = False
    encryption_key: str = field(default="", repr=False)
    clients: list[dict] = field(default_factory=list)
    code_ttl_seconds: int = 120
    access_ttl_seconds: int = 3600

    def __post_init__(self):
        if (
            type(self.code_ttl_seconds) is not int
            or type(self.access_ttl_seconds) is not int
            or not 30 <= self.code_ttl_seconds <= 300
            or not 120 <= self.access_ttl_seconds <= 86400
        ):
            raise ValueError("MCP OAuth lifetimes are outside their supported bounds")
        if not self.enabled:
            return
        try:
            Fernet(self.encryption_key.encode("ascii"))
        except (ValueError, UnicodeError):
            raise ValueError("MCP OAuth requires a valid Fernet encryption key") from None
        identifiers = set()
        for client in self.clients:
            if not isinstance(client, dict) or set(client) - {
                "client_id",
                "name",
                "redirect_uris",
                "scopes",
                "client_secret_hash",
            }:
                raise ValueError("Invalid pre-registered MCP OAuth client")
            identifier, name = client.get("client_id"), client.get("name")
            if (
                not isinstance(identifier, str)
                or not re.fullmatch(r"[A-Za-z0-9._~-]{1,128}", identifier)
                or identifier in identifiers
                or not isinstance(name, str)
                or not 1 <= len(name) <= 120
            ):
                raise ValueError("MCP OAuth clients need unique IDs and readable names")
            identifiers.add(identifier)
            redirects, scopes = client.get("redirect_uris"), client.get("scopes")
            if not isinstance(redirects, list) or not 1 <= len(redirects) <= 8:
                raise ValueError("MCP OAuth clients need exact redirect URIs")
            for redirect in redirects:
                if not isinstance(redirect, str) or len(redirect) > 2048:
                    raise ValueError("Invalid MCP OAuth redirect URI")
                _endpoint(redirect)
            if (
                not isinstance(scopes, list)
                or not scopes
                or len(scopes) > len(MCP_SCOPES)
                or any(not isinstance(scope, str) or scope not in MCP_SCOPES for scope in scopes)
                or "catalog:read" not in scopes
            ):
                raise ValueError("MCP OAuth clients need explicit supported knowledge scopes")
            secret_hash = client.get("client_secret_hash")
            if secret_hash is not None and (
                not isinstance(secret_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", secret_hash)
            ):
                raise ValueError("MCP OAuth client secrets must be SHA-256 digests")
