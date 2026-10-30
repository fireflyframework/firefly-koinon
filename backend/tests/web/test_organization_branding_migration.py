# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError


def test_native19_adds_empty_bounded_branding_without_changing_retained_rows(tmp_path):
    path = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/native_versions/0019_organization_branding.py"
    )
    spec = importlib.util.spec_from_file_location("organization_branding_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.down_revision == "koinon_0018_org_knowledge" and len(module.revision) <= 32
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES ('north')")
        connection.exec_driver_sql(
            "CREATE TABLE koinon_chat_runs (id VARCHAR(64) PRIMARY KEY,status VARCHAR(32))"
        )
        connection.exec_driver_sql("INSERT INTO koinon_chat_runs VALUES ('retained-run','completed')")
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert connection.exec_driver_sql("SELECT * FROM koinon_chat_runs").all() == [
            ("retained-run", "completed")
        ]
        assert connection.exec_driver_sql("SELECT * FROM koinon_organization_branding").all() == []
        insert = (
            "INSERT INTO koinon_organization_branding "
            "(tenant_id,schema_version,revision,branding_json,updated_by,updated_at) "
            "VALUES (?,?,?,?, 'owner','2026-10-29T00:00:00')"
        )
        connection.exec_driver_sql(insert, ("north", 1, 1, "{}"))
        for schema, revision, payload in (
            (2, 2, "{}"),
            (1, 0, "{}"),
            (1, 2147483648, "{}"),
            (1, 2, "x" * 1572865),
        ):
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(
                    "UPDATE koinon_organization_branding SET schema_version=?,revision=?,branding_json=?",
                    (schema, revision, payload),
                )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(insert, ("missing", 1, 1, "{}"))
        connection.exec_driver_sql("UPDATE koinon_organization_branding SET branding_json=NULL,revision=2")
        assert connection.exec_driver_sql(
            "SELECT revision,branding_json FROM koinon_organization_branding"
        ).one() == (2, None)
