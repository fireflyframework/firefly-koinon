# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


def test_registry_migration_preserves_static_history_without_inventing_registration_pins(tmp_path):
    path = Path(__file__).resolve().parents[3] / "deploy/migrations/native_versions/0021_mcp_oauth_clients.py"
    spec = importlib.util.spec_from_file_location("oauth_clients_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "koinon_0020_external_reviews" and len(module.revision) <= 32
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id TEXT PRIMARY KEY)")
        for table in ("koinon_mcp_authorizations", "koinon_authorized_applications"):
            connection.exec_driver_sql(f"CREATE TABLE {table} (id TEXT PRIMARY KEY, retained TEXT)")
            connection.exec_driver_sql(f"INSERT INTO {table} VALUES ('retained','original')")
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        for table in ("koinon_mcp_authorizations", "koinon_authorized_applications"):
            assert connection.exec_driver_sql(
                f"SELECT id,retained,client_registration FROM {table}"
            ).all() == [("retained", "original", None)]
        columns = {column["name"] for column in inspect(connection).get_columns("koinon_mcp_oauth_clients")}
        assert "client_secret_hash" in columns and "client_secret" not in columns
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("INSERT INTO koinon_mcp_oauth_clients(id) VALUES ('invalid')")
