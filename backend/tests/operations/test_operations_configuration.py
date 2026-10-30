# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib
import secrets

import pytest
from pyfly.config.properties.data import RelationalProperties
from pyfly.config.properties.server import resolve_app_port
from pyfly.core import Config


def test_mcp_environment_aliases_are_resolved_without_changing_native_listener(monkeypatch):
    monkeypatch.setenv("KOINON_OIDC_ISSUER", "https://identity.example/realm")
    monkeypatch.setenv("KOINON_DATABASE_URL", "sqlite+aiosqlite:///./configuration-only.db")
    monkeypatch.setenv("KOINON_MCP_ENABLED", "true")
    monkeypatch.setenv("KOINON_MCP_PUBLIC_URL", "https://knowledge.example/mcp")
    monkeypatch.setenv("PYFLY_SERVER_HOST", "127.0.0.1")
    monkeypatch.setenv("PYFLY_SERVER_PORT", "19221")
    from koinon.operations.configuration import environment_configuration

    values = environment_configuration()
    assert values["koinon"]["mcp"]["enabled"] is True
    assert values["koinon"]["mcp"]["public_url"] == "https://knowledge.example/mcp"
    assert resolve_app_port(Config(values)) == 19221
    monkeypatch.setenv("KOINON_MCP_ENABLED", "not-a-boolean")
    with pytest.raises(ValueError):
        environment_configuration()


def test_native_file_preserves_oidc_and_exact_named_pools_until_explicit_alias_override(
    tmp_path, monkeypatch
):
    for name in ("OIDC_ISSUER", "OIDC_CLIENT_SECRET", "DATABASE_URL", "CONFIG_FILE", "MASTER_KEY"):
        monkeypatch.delenv("KOINON_" + name, raising=False)
    monkeypatch.delenv("PYFLY_DATA_RELATIONAL_URL", raising=False)
    key = secrets.token_urlsafe(32)
    monkeypatch.setenv("TEST_OPERATOR_SECRET", key)
    file = tmp_path / "operator.yaml"
    file.write_text("""koinon:
  security:
    issuer: https://identity.example/realms/owned
    jwks_uri: https://identity.example/certs
    authorization_uri: https://identity.example/auth
    token_uri: https://identity.example/token
    redirect_uri: https://knowledge.example/login/oauth2/code/koinon
    client_id: owned-browser
    api_audience: owned-api
    client_secret: ${TEST_OPERATOR_SECRET}
    cookie_secure: true
  legacy:
    enabled: false
pyfly:
  data:
    relational:
      enabled: true
      url: sqlite+aiosqlite:///./operator-test.db
      pool:
        size: 7
        max-overflow: 0
      datasources:
        canon_admin:
          url: postgresql+asyncpg://operator@127.0.0.1:18783/owned
          pool:
            size: 1
            timeout: 4
outside_allowed_sections:
  secret: ignored-private-value
""")
    monkeypatch.setenv("KOINON_CONFIG_FILE", str(file))
    configuration = importlib.import_module("koinon.operations.configuration").environment_configuration()
    assert configuration["koinon"]["security"]["issuer"] == "https://identity.example/realms/owned"
    assert configuration["koinon"]["security"]["client_id"] == "owned-browser"
    matched = secrets.compare_digest(configuration["koinon"]["security"]["client_secret"], key)
    assert matched
    assert "outside_allowed_sections" not in configuration
    properties = RelationalProperties.from_config(Config(configuration))
    assert properties.primary().pool.size == 7
    assert properties.datasources["canon_admin"].pool.size == 1
    assert properties.datasources["canon_admin"].pool.timeout == 4
    monkeypatch.setenv("KOINON_DATABASE_POOL_SIZE", "9")
    monkeypatch.setenv("KOINON_CANON_ADMIN_POOL_TIMEOUT", "2.5")
    updated = importlib.import_module("koinon.operations.configuration").environment_configuration()
    properties = RelationalProperties.from_config(Config(updated))
    assert properties.primary().pool.size == 9 and properties.datasources["canon_admin"].pool.timeout == 2.5


@pytest.mark.parametrize(
    "setting,value",
    [
        ("DATABASE_POOL_SIZE", "0"),
        ("DATABASE_POOL_MAX_OVERFLOW", "-1"),
        ("CANON_ADMIN_POOL_TIMEOUT", "nan"),
        ("WORKER_CONCURRENCY", "0"),
        ("TOKEN_MAX_ACTIVE_PER_USER", "0"),
        ("ASSISTANT_LEASE_SECONDS", "-1"),
    ],
)
def test_scaling_aliases_reject_invalid_or_unbounded_settings(monkeypatch, setting, value):
    monkeypatch.setenv("KOINON_OIDC_ISSUER", "https://identity.example/realm")
    monkeypatch.setenv("KOINON_DATABASE_URL", "sqlite+aiosqlite:///./limits-test.db")
    monkeypatch.setenv("KOINON_LEGACY_ENABLED", "false")
    module = importlib.import_module("koinon.operations.configuration")
    monkeypatch.setenv("KOINON_" + setting, value)
    with pytest.raises(ValueError):
        module.environment_configuration()


def test_missing_explicit_file_fails_without_exposing_operator_path(tmp_path, monkeypatch):
    monkeypatch.setenv("KOINON_CONFIG_FILE", str(tmp_path / "private-operator-file.yaml"))
    monkeypatch.setenv("KOINON_DATABASE_URL", "sqlite+aiosqlite:///./otherwise-valid.db")
    from koinon.operations.configuration import environment_configuration

    with pytest.raises(ValueError) as error:
        environment_configuration()
    assert str(error.value) == "Could not load the operator configuration file"
