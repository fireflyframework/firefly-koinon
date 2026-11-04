# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_mode_migration_preserves_settings_and_enforces_single_active_request(tmp_path):
    path = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/native_versions/0044_knowledge_mode_transitions.py"
    )
    spec = importlib.util.spec_from_file_location("mode_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "koinon_0043_ordinary_folders"
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'migration.db'}")
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE lattice_jobs (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE koinon_organization_knowledge_settings (tenant_id TEXT PRIMARY KEY, documents TEXT)"
        )
        connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES ('tenant')")
        connection.exec_driver_sql(
            "INSERT INTO koinon_organization_knowledge_settings VALUES ('tenant', 'original-policy')"
        )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert (
            connection.exec_driver_sql(
                "SELECT documents FROM koinon_organization_knowledge_settings"
            ).scalar_one()
            == "original-policy"
        )
        inspector = sa.inspect(connection)
        assert {"koinon_knowledge_mode_transitions", "koinon_knowledge_mode_targets"} <= set(
            inspector.get_table_names()
        )
        assert {"active_slot"} in [
            set(item["column_names"])
            for item in inspector.get_unique_constraints("koinon_knowledge_mode_transitions")
        ]
        foreign = inspector.get_foreign_keys("koinon_knowledge_mode_targets")
        assert any(item["constrained_columns"] == ["tenant_id", "transition_id"] for item in foreign)
    engine.dispose()
