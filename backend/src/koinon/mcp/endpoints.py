# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Resolve MCP endpoints from trusted configuration and native listener metadata."""
import ipaddress
import os
import re
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from pyfly.config.properties.data import parse_bool
from pyfly.config.properties.server import ServerProperties, resolve_app_host, resolve_app_port
from pyfly.core import Config

from koinon.security.settings import _endpoint


def is_local_host(host: str | None) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host or "").is_loopback
    except ValueError:
        return False


def validate_mcp_url(value: str) -> None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > 2048
        or any(char.isspace() or ord(char) < 32 or char == "\\" for char in value)
    ):
        raise ValueError("Configure an absolute MCP endpoint without whitespace or control characters")
    try:
        _endpoint(value)
        parsed = urlsplit(value)
        if parsed.path != "/mcp" or parsed.query or parsed.port == 0:
            raise ValueError()
        try:
            address = ipaddress.ip_address(parsed.hostname or "")
        except ValueError:
            if re.fullmatch(r"[0-9.]+", parsed.hostname or ""):
                raise ValueError() from None
        else:
            if address.is_unspecified:
                raise ValueError()
    except ValueError:
        raise ValueError(
            "MCP endpoint requires an explicit host and exact /mcp path without query or fragment"
        ) from None


def listener_properties(config: Config) -> ServerProperties:
    actual_host, actual_port = os.environ.get("_PYFLY_SERVER_HOST"), os.environ.get("_PYFLY_SERVER_PORT")
    if (actual_host is None) != (actual_port is None):
        raise ValueError("Native listener metadata requires both host and port")
    host = actual_host if actual_host is not None else config.get("pyfly.server.host", "0.0.0.0")
    port = actual_port if actual_port is not None else config.get("pyfly.server.port", 8080)
    if not isinstance(host, str) or not host or len(host) > 253 or "%" in host:
        raise ValueError("Configure a plain application listener host")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if (re.fullmatch(r"[0-9.]+", host)
                or not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?", host)):
            raise ValueError("Configure a plain application listener host") from None
        if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-")
               for label in host.split(".")):
            raise ValueError("Configure a valid application listener host") from None
    if type(port) is not int and not (isinstance(port, str) and port.isascii() and port.isdecimal()):
        raise ValueError("Configure an integer application listener port")
    if not 1 <= int(port) <= 65535:
        raise ValueError("Application listener port must be between 1 and 65535")
    properties = config.bind(ServerProperties)
    properties.host = host if actual_host is not None else resolve_app_host(config)
    properties.port = int(port) if actual_port is not None else resolve_app_port(config)
    cert, key = properties.ssl_certfile, properties.ssl_keyfile
    if bool(cert) != bool(key):
        raise ValueError("Native HTTPS requires both certificate and key paths")
    if cert and key:
        for path in (cert, key):
            if not isinstance(path, str) or any(char in path for char in ("\0", "\r", "\n")):
                raise ValueError("Configure valid native TLS file paths")
            if not Path(path).is_file():
                raise ValueError("Native TLS certificate and key files must exist")
    return properties


def resolve_mcp_configuration(values: dict) -> dict:
    resolved = deepcopy(values)
    config = Config(resolved)
    enabled_alias = os.environ.get("KOINON_MCP_ENABLED")
    native_enabled = os.environ.get("PYFLY_KOINON_MCP_ENABLED")
    if enabled_alias is not None and native_enabled is not None and (
        parse_bool(enabled_alias, "KOINON_MCP_ENABLED")
        != parse_bool(native_enabled, "PYFLY_KOINON_MCP_ENABLED")
    ):
        raise ValueError("MCP enabled environment aliases disagree")
    enabled = enabled_alias if enabled_alias is not None else config.get("koinon.mcp.enabled", False)
    if not parse_bool(enabled, "koinon.mcp.enabled"):
        resolved.setdefault("koinon", {}).setdefault("mcp", {})["enabled"] = False
        return resolved
    endpoint_alias = os.environ.get("KOINON_MCP_PUBLIC_URL")
    native_endpoint = os.environ.get("PYFLY_KOINON_MCP_PUBLIC_URL")
    if endpoint_alias is not None and native_endpoint is not None and endpoint_alias != native_endpoint:
        raise ValueError("MCP endpoint environment aliases disagree")
    endpoint = endpoint_alias if endpoint_alias is not None else config.get("koinon.mcp.public_url", "")
    if not isinstance(endpoint, str):
        raise ValueError("MCP public_url must be a string")
    if not endpoint:
        properties = listener_properties(config)
        host = properties.host
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            pass
        else:
            if address.is_unspecified:
                host = "::1" if address.version == 6 else "127.0.0.1"
        authority = f"[{host}]" if ":" in host else host
        scheme = "https" if properties.ssl_certfile else "http"
        endpoint = f"{scheme}://{authority}:{properties.port}/mcp"
    validate_mcp_url(endpoint)
    resolved.setdefault("koinon", {}).setdefault("mcp", {}).update(enabled=True, public_url=endpoint)
    return resolved
