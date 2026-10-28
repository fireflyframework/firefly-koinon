# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import ipaddress
from dataclasses import dataclass, field
from urllib.parse import urlsplit

from pyfly.core import config_properties


def _endpoint(value: str) -> None:
    parsed = urlsplit(value)
    if not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("OIDC endpoints must be absolute URLs without credentials or fragments")
    try:
        local = ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = parsed.hostname == "localhost"
    if parsed.scheme != "https" and not (parsed.scheme == "http" and local):
        raise ValueError("OIDC endpoints require HTTPS; HTTP is restricted to loopback development")
    _ = parsed.port


@config_properties(prefix="koinon.security")
@dataclass
class OidcSettings:
    issuer: str
    jwks_uri: str
    client_id: str
    api_audience: str
    authorization_uri: str
    token_uri: str
    redirect_uri: str
    client_secret: str = field(default="", repr=False)
    cookie_secure: bool = True
    require_iss: bool = False
    success_uri: str = "/"

    def __post_init__(self) -> None:
        for value in (self.issuer, self.jwks_uri, self.authorization_uri, self.token_uri, self.redirect_uri):
            _endpoint(value)
        if not (
            self.success_uri.startswith("/")
            and not self.success_uri.startswith("//")
            and "\\" not in self.success_uri
        ):
            _endpoint(self.success_uri)
        if not self.client_id or not self.api_audience or "|" in self.issuer:
            raise ValueError("OIDC client, API audience, and canonical issuer must be configured")
        if not self.cookie_secure and urlsplit(self.redirect_uri).hostname not in (
            "127.0.0.1",
            "localhost",
            "::1",
        ):
            raise ValueError("Insecure session cookies are restricted to loopback development")
