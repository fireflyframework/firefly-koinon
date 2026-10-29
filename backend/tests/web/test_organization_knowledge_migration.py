# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


def test_native18_preserves_chat_history_adds_nullable_snapshot_and_empty_tenant_policy(tmp_path):
    path = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/native_versions/0018_organization_knowledge.py"
    )
    assert path.is_file(), "The additive native18 knowledge settings migration is missing"
    spec = importlib.util.spec_from_file_location("org_knowledge_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "koinon_0017_org_chat" and len(module.revision) <= 32
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES ('north')")
        connection.exec_driver_sql("CREATE TABLE koinon_agents (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO koinon_agents VALUES ('retained-agent')")
        connection.exec_driver_sql(
            "CREATE TABLE koinon_chat_runs (id VARCHAR(64) PRIMARY KEY, "
            "agent_id VARCHAR(64) REFERENCES koinon_agents(id), status VARCHAR(32))"
        )
        connection.exec_driver_sql(
            "INSERT INTO koinon_chat_runs VALUES ('retained-run','retained-agent','completed')"
        )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert connection.exec_driver_sql(
            "SELECT id,agent_id,status,knowledge_settings_snapshot FROM koinon_chat_runs"
        ).all() == [("retained-run", "retained-agent", "completed", None)]
        assert connection.exec_driver_sql("SELECT * FROM koinon_organization_knowledge_settings").all() == []
        assert any(
            fk["referred_table"] == "koinon_agents"
            for fk in inspect(connection).get_foreign_keys("koinon_chat_runs")
        )
        insert = (
            "INSERT INTO koinon_organization_knowledge_settings "
            "(tenant_id,schema_version,revision,documents,structured,updated_by,updated_at) "
            "VALUES (?,?,?,'{}','{}','owner','2026-10-29T00:00:00')"
        )
        connection.exec_driver_sql(insert, ("north", 1, 1))
        for tenant, schema, revision in (
            ("missing", 1, 1),
            ("north", 2, 2),
            ("north", 1, 0),
            ("north", 1, 2147483648),
        ):
            with pytest.raises(IntegrityError):
                if tenant == "missing":
                    connection.exec_driver_sql(insert, (tenant, schema, revision))
                else:
                    connection.exec_driver_sql(
                        "UPDATE koinon_organization_knowledge_settings SET schema_version=?,revision=?",
                        (schema, revision),
                    )
