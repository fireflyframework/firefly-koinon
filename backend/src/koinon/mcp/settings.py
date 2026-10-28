# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from mcp.server.transport_security import TransportSecuritySettings
from pyfly.core import config_properties

from koinon.security.settings import _endpoint


@config_properties(prefix="koinon.mcp")
@dataclass
class McpSettings:
    enabled: bool = False
    public_url: str = ""
    allowed_hosts: list[str] = field(default_factory=list)
    allowed_origins: list[str] = field(default_factory=list)
    max_request_bytes: int = 131072
    max_response_bytes: int = 2097152
    timeout_seconds: float = 30
    max_concurrency: int = 8

    def __post_init__(self):
        if self.enabled:
            if not self.public_url:
                raise ValueError("MCP public_url is required when enabled")
            _endpoint(self.public_url)
            parsed = urlsplit(self.public_url)
            if parsed.path != "/mcp" or parsed.query:
                raise ValueError("MCP public_url must have the exact /mcp path without query")
            for value in self.allowed_hosts:
                if not value or any(c in value for c in "/\\@*?#"):
                    raise ValueError("MCP hosts must be explicit authorities")
            for value in self.allowed_origins:
                _endpoint(value)
                origin = urlsplit(value)
                if origin.path or origin.query:
                    raise ValueError("MCP origins must be explicit scheme and authority")
        if not (
            1024 <= self.max_request_bytes <= 1048576
            and 1024 <= self.max_response_bytes <= 16777216
            and 1 <= self.timeout_seconds <= 120
            and 1 <= self.max_concurrency <= 64
        ):
            raise ValueError("MCP runtime limits are outside supported bounds")

    def transport_security(self):
        parsed = urlsplit(self.public_url)
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=list(dict.fromkeys([parsed.netloc, *self.allowed_hosts])),
            allowed_origins=list(
                dict.fromkeys([f"{parsed.scheme}://{parsed.netloc}", *self.allowed_origins])
            ),
        )
