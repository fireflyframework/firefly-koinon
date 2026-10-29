# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError


def test_organization_default_migration_preserves_agents_and_enforces_tenant_pair(tmp_path):
    path = Path(__file__).resolve().parents[3] / "deploy/migrations/native_versions/0017_organization_chat.py"
    spec = importlib.util.spec_from_file_location("org_chat_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "koinon_0016_authorized_apps" and len(module.revision) <= 32
    engine = create_engine("sqlite:///" + str(tmp_path / "org.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE koinon_agents (id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL)"
        )
        connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES ('north'),('south')")
        connection.exec_driver_sql("INSERT INTO koinon_agents VALUES ('retained','north')")
        connection.exec_driver_sql("CREATE TABLE retained_runs (agent_id TEXT REFERENCES koinon_agents(id))")
        connection.exec_driver_sql("INSERT INTO retained_runs VALUES ('retained')")
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert connection.exec_driver_sql("SELECT * FROM koinon_agents").all() == [("retained", "north")]
        assert connection.exec_driver_sql("SELECT * FROM koinon_organization_chat_settings").all() == []
        statement = (
            "INSERT INTO koinon_organization_chat_settings VALUES (?,?,1,'owner','2026-10-28T00:00:00')"
        )
        connection.exec_driver_sql(statement, ("north", "retained"))
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(statement, ("south", "retained"))
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("UPDATE koinon_organization_chat_settings SET revision=0")
