# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from koinon.corporate_identity.settings import IdentitySettings
from koinon.operations.configuration import environment_configuration


def test_identity_credentials_have_explicit_separate_deployment_aliases(monkeypatch):
    monkeypatch.delenv("KOINON_CONFIG_FILE", raising=False)
    monkeypatch.setenv("KOINON_OIDC_ISSUER", "https://identity.test/realms/owned")
    monkeypatch.setenv("KOINON_DATABASE_URL", "sqlite+aiosqlite:///./not-opened.db")
    monkeypatch.setenv("KOINON_LEGACY_ENABLED", "false")
    monkeypatch.setenv("KOINON_MASTER_KEY", "assistant-purpose-only")
    monkeypatch.setenv("KOINON_IDENTITY_MASTER_KEY", "identity-purpose-only")
    monkeypatch.setenv("KOINON_IDENTITY_BROKER_ADMIN_CLIENT_ID", "broker-read-only")
    monkeypatch.setenv("KOINON_IDENTITY_BROKER_ADMIN_SECRET", "synthetic-broker-secret")
    monkeypatch.setenv("KOINON_IDENTITY_ALLOWED_PROVIDER_HOSTS", '["identity.test"]')
    monkeypatch.setenv("KOINON_IDENTITY_SNAPSHOT_TTL_SECONDS", "120")
    result = environment_configuration()
    settings = IdentitySettings(**result["koinon"]["identity"])
    assert settings.master_key == "identity-purpose-only"
    assert result["koinon"]["assistants"]["master_key"] == "assistant-purpose-only"
    assert settings.allowed_provider_hosts == ["identity.test"] and settings.snapshot_ttl_seconds == 120
    assert settings.broker_admin_client_id == "broker-read-only"
    assert "synthetic-broker-secret" not in repr(settings) and "identity-purpose-only" not in repr(settings)
