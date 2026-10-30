# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Configured listener resolution only. No test opens a listener or uses a request Host."""
import importlib
import shlex
from pathlib import Path

import pytest
from pyfly.core import Config


@pytest.fixture(autouse=True)
def clean_listener_environment(monkeypatch):
    for name in (
        "PYFLY_SERVER_HOST", "PYFLY_SERVER_PORT", "PYFLY_SERVER_SSL_CERTFILE",
        "PYFLY_SERVER_SSL_KEYFILE", "_PYFLY_SERVER_HOST", "_PYFLY_SERVER_PORT",
        "KOINON_MCP_ENABLED", "KOINON_MCP_PUBLIC_URL", "_PYFLY_SERVER_TYPE",
        "PYFLY_KOINON_MCP_ENABLED", "PYFLY_KOINON_MCP_PUBLIC_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def resolve(server=None, **mcp):
    from koinon.mcp.endpoints import resolve_mcp_configuration

    values = {"pyfly": {"server": server or {}}, "koinon": {"mcp": {"enabled": True, **mcp}}}
    result = resolve_mcp_configuration(values)
    assert values["koinon"]["mcp"] == {"enabled": True, **mcp}
    from koinon.mcp.settings import McpSettings

    return Config(result).bind(McpSettings)


@pytest.mark.parametrize("host,advertised", [
    ("0.0.0.0", "127.0.0.1"), ("127.0.0.1", "127.0.0.1"),
    ("localhost", "localhost"), ("::", "[::1]"), ("::1", "[::1]"),
    ("0:0:0:0:0:0:0:0", "[::1]"),
])
def test_actual_native_listener_has_a_safe_local_endpoint(host, advertised):
    settings = resolve({"host": host, "port": 18781})
    assert settings.public_url == f"http://{advertised}:18781/mcp"
    assert settings.local_only is True
    assert advertised + ":18781" in settings.transport_security().allowed_hosts


def test_native_defaults_and_environment_are_the_same_listener_source(monkeypatch):
    assert resolve().public_url == "http://127.0.0.1:8080/mcp"
    monkeypatch.setenv("PYFLY_SERVER_HOST", "127.0.0.2")
    monkeypatch.setenv("PYFLY_SERVER_PORT", "19443")
    assert resolve({"port": 8080}).public_url == "http://127.0.0.2:19443/mcp"


def test_explicit_endpoint_has_precedence_over_listener_and_never_uses_headers(monkeypatch):
    monkeypatch.setenv("HTTP_HOST", "attacker.invalid")
    monkeypatch.setenv("HTTP_FORWARDED", "host=attacker.invalid;proto=https")
    settings = resolve({"host": "0.0.0.0", "port": 8080}, public_url="https://knowledge.example/mcp")
    assert settings.public_url == "https://knowledge.example/mcp" and not settings.local_only
    monkeypatch.setenv("KOINON_MCP_PUBLIC_URL", "https://configured.example/mcp")
    assert resolve(public_url="https://knowledge.example/mcp").public_url == "https://configured.example/mcp"


def test_native_cli_actual_listener_pair_is_used_without_guessing(monkeypatch):
    from koinon.mcp.endpoints import resolve_mcp_configuration

    monkeypatch.setenv("_PYFLY_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("_PYFLY_SERVER_PORT", "19222")
    values = resolve_mcp_configuration({"koinon": {"mcp": {"enabled": True}}})
    assert values["koinon"]["mcp"]["public_url"] == "http://127.0.0.1:19222/mcp"


def test_partial_native_runtime_listener_metadata_is_rejected(monkeypatch):
    monkeypatch.setenv("_PYFLY_SERVER_PORT", "18781")
    with pytest.raises(ValueError):
        resolve()


@pytest.mark.parametrize("url", [
    "https://knowledge.example/mcp/", "https://knowledge.example/not-mcp",
    "https://knowledge.example/mcp?x=1", "https://knowledge.example/mcp#fragment",
    "https://user:secret@knowledge.example/mcp", "https://0.0.0.0/mcp",
    "https://[::]/mcp", "http://knowledge.example/mcp", " https://knowledge.example/mcp",
    "https://knowledge.example\\evil/mcp",
    "https://knowledge.example:0/mcp",
    "https://[0:0:0:0:0:0:0:0]/mcp", "https://0/mcp",
])
def test_explicit_invalid_or_unroutable_endpoints_fail_closed(url):
    with pytest.raises(ValueError):
        resolve(public_url=url)


@pytest.mark.parametrize("server", [
    {"host": ""}, {"host": "unix:/socket"}, {"host": "host/path"}, {"host": "0"},
    {"port": 0}, {"port": 65536}, {"port": True}, {"port": 1.5},
    {"host": "10.0.0.5"}, {"ssl_certfile": "/missing/cert.pem"},
    {"ssl_certfile": "/missing/cert.pem", "ssl_keyfile": "/missing/key.pem"},
])
def test_ambiguous_or_invalid_listener_configuration_is_rejected(server):
    with pytest.raises(ValueError):
        resolve(server)


def test_tls_pair_uses_native_server_properties_without_reading_key_bytes(tmp_path):
    cert, key = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert.write_text("owned opaque certificate-path fixture")
    key.write_text("owned opaque key-path fixture")
    settings = resolve({"host": "127.0.0.1", "port": 19443,
                        "ssl_certfile": str(cert), "ssl_keyfile": str(key)})
    assert settings.public_url == "https://127.0.0.1:19443/mcp" and settings.local_only


def test_disabled_mcp_does_not_require_or_invent_an_endpoint():
    from koinon.mcp.endpoints import resolve_mcp_configuration

    assert resolve_mcp_configuration({"koinon": {"mcp": {"enabled": False}}}) == {
        "koinon": {"mcp": {"enabled": False}}
    }


def test_disabled_alias_and_native_environment_configuration_are_consistent(monkeypatch):
    monkeypatch.setenv("KOINON_MCP_ENABLED", "false")
    assert not resolve().enabled
    monkeypatch.delenv("KOINON_MCP_ENABLED")
    monkeypatch.setenv("PYFLY_KOINON_MCP_ENABLED", "true")
    monkeypatch.setenv("PYFLY_KOINON_MCP_PUBLIC_URL", "https://native.example/mcp")
    assert resolve(enabled=False).public_url == "https://native.example/mcp"


@pytest.mark.parametrize("key,native,value", [
    ("KOINON_MCP_ENABLED", "PYFLY_KOINON_MCP_ENABLED", "false"),
    ("KOINON_MCP_PUBLIC_URL", "PYFLY_KOINON_MCP_PUBLIC_URL", "https://other.example/mcp"),
])
def test_conflicting_explicit_environment_aliases_are_rejected(monkeypatch, key, native, value):
    monkeypatch.setenv(key, "true" if key.endswith("ENABLED") else "https://configured.example/mcp")
    monkeypatch.setenv(native, value)
    with pytest.raises(ValueError):
        resolve()


@pytest.mark.parametrize("options", [
    {"max_sessions": 0}, {"max_sessions": 4097}, {"max_sessions": True},
    {"session_idle_timeout_seconds": 29}, {"session_idle_timeout_seconds": 3601},
    {"session_idle_timeout_seconds": float("nan")},
    {"session_idle_timeout_seconds": 10**1000},
])
def test_native_mcp_stateful_session_limits_are_bounded(options):
    from koinon.mcp.settings import McpSettings

    with pytest.raises(ValueError):
        McpSettings(**options)


def test_native_serve_passes_the_same_properties_to_the_public_pyfly_adapter(monkeypatch):
    from pyfly.server.adapters.uvicorn.adapter import UvicornServerAdapter
    from pyfly.server.ports.outbound import ApplicationServerPort

    module = importlib.import_module("koinon.serve")
    values = {"pyfly": {"server": {"type": "uvicorn", "event_loop": "asyncio",
                                   "host": "127.0.0.1", "port": 19221}},
              "koinon": {"mcp": {"enabled": True}}}
    monkeypatch.setattr(module, "environment_configuration", lambda: values)
    monkeypatch.setenv("_PYFLY_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("_PYFLY_SERVER_PORT", "19221")
    monkeypatch.setenv("_PYFLY_SERVER_TYPE", "uvicorn")
    seen = []

    def observe(adapter, app, properties):
        assert isinstance(adapter, ApplicationServerPort)
        seen.append((app, properties))

    monkeypatch.setattr(UvicornServerAdapter, "serve", observe)
    module.main()
    assert len(seen) == 1
    app, properties = seen[0]
    assert app == "koinon.main:app"
    assert (properties.host, properties.port) == ("127.0.0.1", 19221)
    assert resolve({"host": properties.host, "port": properties.port}).public_url == "http://127.0.0.1:19221/mcp"


def test_native_server_choice_rejects_unknown_adapters_without_fallback():
    from koinon.serve import application_server, event_loop

    with pytest.raises(ValueError):
        application_server("unknown")
    with pytest.raises(ValueError):
        event_loop("unknown")


def test_production_native_uvicorn_preserves_loopback_proxy_trust(monkeypatch):
    import uvicorn
    from pyfly.server.auto_configuration import ServerAutoConfiguration

    from koinon.mcp.endpoints import listener_properties

    unit = (Path(__file__).resolve().parents[3] / "deploy/production/backend.service").read_text()
    assert "Environment=PYFLY_SERVER_TYPE=uvicorn" in unit
    command = shlex.split(next(line.removeprefix("ExecStart=") for line in unit.splitlines()
                               if line.startswith("ExecStart=")))
    assert command[:2] == ["/usr/bin/env", "FORWARDED_ALLOW_IPS=127.0.0.1"]
    monkeypatch.setenv("FORWARDED_ALLOW_IPS", "*")
    key, value = command[1].split("=", 1)
    monkeypatch.setenv(key, value)
    observed = []

    def inspect(app, **kwargs):
        configuration = uvicorn.Config(app, **kwargs)
        observed.append((configuration.proxy_headers, configuration.forwarded_allow_ips))

    monkeypatch.setattr(uvicorn, "run", inspect)
    ServerAutoConfiguration().uvicorn_server().serve(
        "owned-fixture:app", listener_properties(Config({"pyfly": {"server": {"host": "127.0.0.1"}}}))
    )
    assert observed == [(True, "127.0.0.1")]
