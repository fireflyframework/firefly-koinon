# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Private local configuration boundaries; these tests do not start infrastructure."""

import base64
import importlib.util
import stat
from pathlib import Path

import pytest

DEPLOY = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "local_configuration", DEPLOY / "generate_local_configuration.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_generated_configuration_separates_migration_authority_and_encryption_key(
    tmp_path,
):
    directory = module.generate(tmp_path / "private")
    runtime = dict(
        line.split("=", 1)
        for line in (directory / "runtime.env").read_text().splitlines()
    )
    migration = dict(
        line.split("=", 1)
        for line in (directory / "migration.env").read_text().splitlines()
    )
    assert "KOINON_MIGRATION_DATABASE_URL" not in runtime
    assert "KOINON_MASTER_KEY" not in migration
    assert len(base64.urlsafe_b64decode(runtime["KOINON_MASTER_KEY"])) == 32
    assert (directory / "master_key").read_text().strip() == runtime[
        "KOINON_MASTER_KEY"
    ]
    assert (
        len(
            {
                value.split("@")[0]
                for key, value in runtime.items()
                if key.startswith("KOINON_") and key.endswith("DATABASE_URL")
            }
        )
        == 5
    )
    assert stat.S_IMODE(directory.stat().st_mode) == 0o700
    assert all(
        stat.S_IMODE(path.stat().st_mode) == 0o600 for path in directory.iterdir()
    )
    with pytest.raises(FileExistsError):
        module.generate(directory)
    assert (directory / "runtime.env").read_text().startswith("KOINON_OIDC_ISSUER=")


def test_fresh_structured_bootstrap_has_no_executable_default_password():
    migration = DEPLOY.parent / "packages/structured/migrations/versions/0007_rls.py"
    source = migration.read_text()
    assert "CREATE ROLE flyquery_admin NOLOGIN BYPASSRLS" in source
    assert "CREATE ROLE flyquery_app NOLOGIN NOSUPERUSER NOBYPASSRLS" in source
    assert "PASSWORD '" not in source


def test_first_local_startup_binds_the_listener_announced_to_mcp(tmp_path):
    directory = module.generate(tmp_path / "new-private")
    runtime = dict(
        line.split("=", 1)
        for line in (directory / "runtime.env").read_text().splitlines()
    )
    assert runtime["PYFLY_SERVER_HOST"] == "127.0.0.1"
    assert runtime["PYFLY_SERVER_PORT"] == "18781"
    assert runtime["KOINON_MCP_ENABLED"] == "true"
    assert "KOINON_MCP_PUBLIC_URL" not in runtime
    service = (DEPLOY / "production/backend.service").read_text()
    assert "-m koinon.serve" in service
    assert "-m uvicorn" not in service


def test_first_startup_provisions_a_dedicated_oauth_key_with_an_empty_registration_registry(
    tmp_path,
):
    from cryptography.fernet import Fernet

    directory = module.generate(tmp_path / "oauth-private")
    runtime = dict(
        line.split("=", 1)
        for line in (directory / "runtime.env").read_text().splitlines()
    )
    assert runtime["KOINON_MCP_OAUTH_ENABLED"] == "true"
    key = runtime["KOINON_MCP_OAUTH_ENCRYPTION_KEY"]
    assert key != runtime["KOINON_MASTER_KEY"]
    assert (directory / "mcp_oauth_key").read_text().strip() == key
    assert (
        Fernet(key.encode()).decrypt(Fernet(key.encode()).encrypt(b"private"))
        == b"private"
    )
    assert not any("CLIENTS" in name for name in runtime)
    assert "MCP_OAUTH" not in (directory / "migration.env").read_text()


def test_backup_preserves_explicit_tls_options_and_rejects_unknown_options():
    from sqlalchemy.engine import make_url

    spec = importlib.util.spec_from_file_location(
        "backup_configuration", DEPLOY / "backup.py"
    )
    backup = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(backup)
    environment = backup.postgres_environment(
        make_url(
            "postgresql://operator@db.example/knowledge?sslmode=verify-full&sslrootcert=/private/ca.pem"
        )
    )
    assert environment["PGSSLMODE"] == "verify-full"
    assert environment["PGSSLROOTCERT"] == "/private/ca.pem"
    with pytest.raises(ValueError):
        backup.postgres_environment(
            make_url("postgresql://operator@db.example/knowledge?unknown=option")
        )
