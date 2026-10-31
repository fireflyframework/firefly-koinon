# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Additive conversation memory preserves retained rows and defaults to private history."""

import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def test_memory_upgrade_retains_old_conversations_and_defaults_off():
    path = Path(__file__).resolve().parents[1] / "migrations/native_versions/0025_personal_memory.py"
    spec = importlib.util.spec_from_file_location("personal_memory_upgrade", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.down_revision == "koinon_0024_bulk"
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE koinon_organization_chat_settings (tenant_id VARCHAR(64) PRIMARY KEY, default_agent_id VARCHAR(64))")
        connection.exec_driver_sql("CREATE TABLE koinon_chat_threads (id VARCHAR(64) PRIMARY KEY, title VARCHAR(160))")
        connection.exec_driver_sql("CREATE TABLE koinon_chat_folders (id VARCHAR(64) PRIMARY KEY, name VARCHAR(120))")
        connection.exec_driver_sql("INSERT INTO koinon_chat_threads VALUES ('retained-thread', 'Original title')")
        connection.exec_driver_sql("INSERT INTO koinon_chat_folders VALUES ('retained-folder', 'Original folder')")
        connection.exec_driver_sql("INSERT INTO koinon_organization_chat_settings VALUES ('retained-tenant', 'retained-agent')")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        assert connection.exec_driver_sql("SELECT id,title,deleted_at FROM koinon_chat_threads").all() == [("retained-thread", "Original title", None)]
        assert connection.exec_driver_sql("SELECT id,name,memory_enabled FROM koinon_chat_folders").all() == [("retained-folder", "Original folder", 0)]
        assert connection.exec_driver_sql("SELECT tenant_id,default_agent_id,memory_policy_json FROM koinon_organization_chat_settings").all() == [("retained-tenant", "retained-agent", None)]
        inspector = sa.inspect(connection)
        keys = inspector.get_foreign_keys("koinon_chat_memory_manifests")
        assert not any("folder_id" in key["constrained_columns"] for key in keys)
        assert inspector.get_unique_constraints("koinon_chat_memory_manifests")[0]["column_names"] == ["generation_id"]
    engine.dispose()
