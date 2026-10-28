# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib
import secrets


def test_named_datasources_are_explicit_and_migration_credentials_stay_separate(monkeypatch):
    monkeypatch.setenv("KOINON_OIDC_ISSUER", "http://127.0.0.1:18784/realms/koinon")
    monkeypatch.setenv("KOINON_LEGACY_ENABLED", "false")
    monkeypatch.setenv("KOINON_DATABASE_URL", "sqlite+aiosqlite:///./environment-test.db")
    monkeypatch.delenv("PYFLY_DATA_RELATIONAL_URL", raising=False)
    monkeypatch.delenv("KOINON_ASSISTANTS_ALLOWED_PROVIDER_HOSTS", raising=False)
    monkeypatch.delenv("KOINON_ASSISTANTS_ALLOWED_PROVIDER_HOSTS", raising=False)
    monkeypatch.delenv("KOINON_MASTER_KEY", raising=False)
    monkeypatch.delenv("KOINON_MASTER_KEY", raising=False)
    names = ("canon", "canon_admin", "structured", "structured_admin")
    expected = {}
    for name in names:
        value = f"postgresql+asyncpg://{name}:{secrets.token_urlsafe(24)}@127.0.0.1:18783/test"
        monkeypatch.setenv("KOINON_" + name.upper() + "_DATABASE_URL", value)
        expected[name] = {"url": value}
    private = f"postgresql+asyncpg://migrator:{secrets.token_urlsafe(24)}@127.0.0.1:18783/test"
    monkeypatch.setenv("KOINON_MIGRATION_DATABASE_URL", private)
    configuration = importlib.import_module("koinon.main").environment_configuration()
    actual = configuration["pyfly"]["data"]["relational"]["datasources"]
    assert set(actual) == set(expected)
    for name in names:
        matched = secrets.compare_digest(actual[name]["url"], expected[name]["url"])
        assert matched
        assert actual[name]["pool"]["size"] == (1 if name.endswith("_admin") else 2)
        assert actual[name]["pool"]["max-overflow"] == 0
    leaked = private in repr(configuration)
    assert not leaked
    assert configuration["koinon"]["assistants"]["allowed_provider_hosts"] == []
    key = secrets.token_urlsafe(32)
    monkeypatch.setenv("KOINON_MASTER_KEY", key)
    monkeypatch.setenv("KOINON_ASSISTANTS_ALLOWED_PROVIDER_HOSTS", '["model.example"]')
    configured = importlib.import_module("koinon.main").environment_configuration()
    matched = secrets.compare_digest(configured["koinon"]["assistants"]["master_key"], key)
    assert matched
    assert configured["koinon"]["assistants"]["allowed_provider_hosts"] == ["model.example"]
