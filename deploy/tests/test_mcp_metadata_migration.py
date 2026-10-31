# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_shared_mcp_metadata_migration_is_additive_and_matches_native_schema():
    path = Path(__file__).parents[1] / "migrations/native_versions/0026_mcp_sessions.py"
    spec = importlib.util.spec_from_file_location("shared_mcp_metadata_upgrade", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "koinon_0025_memory"
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE retained_source (id TEXT PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO retained_source VALUES ('same-preserved-source')"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert (
                connection.exec_driver_sql("SELECT id FROM retained_source").scalar()
                == "same-preserved-source"
            )
            inspector = sa.inspect(connection)
            assert {"pyfly_mcp_sessions", "pyfly_mcp_session_admission"} <= set(
                inspector.get_table_names()
            )
            columns = {
                item["name"] for item in inspector.get_columns("pyfly_mcp_sessions")
            }
            assert {
                "owner_hash",
                "resource_hash",
                "client_params",
                "initialized",
                "expires_at",
                "schema_version",
                "revision",
            } <= columns
            assert not columns & {"bearer", "token", "response", "transport"}
    finally:
        engine.dispose()
