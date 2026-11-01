# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect


def load(name):
    path = Path(__file__).resolve().parents[4] / "deploy/migrations/native_versions" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_additive_large_file_migration_retains_published_uploads_and_never_credits_quota(tmp_path):
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_tenants(id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE lattice_catalog(id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE lattice_jobs(id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE koinon_external_file_reviews(id VARCHAR(64) PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            load("0024_bulk_intake.py").upgrade()
            connection.exec_driver_sql("INSERT INTO koinon_bulk_quotas VALUES ('tenant:retained',8,1)")
            connection.exec_driver_sql(
                "INSERT INTO koinon_bulk_uploads "
                "(id,item_id,key_hash,object_key,status,permit_held,created_at) "
                "VALUES ('retained','item','key','original','verified',0,CURRENT_TIMESTAMP)"
            )
            before = connection.exec_driver_sql("SELECT * FROM koinon_bulk_uploads").one()
            migration = load("0032_large_files.py")
            assert (
                migration.revision == "koinon_0032_large_files"
                and migration.down_revision == "koinon_0031_activity"
            )
            migration.upgrade()
            assert connection.exec_driver_sql("SELECT * FROM koinon_bulk_uploads").one()[:-1] == before
            assert (
                connection.exec_driver_sql("SELECT reserved_bytes FROM koinon_bulk_quotas").scalar_one() == 8
            )
            assert "object_reference_json" in {
                column["name"] for column in inspect(connection).get_columns("koinon_bulk_uploads")
            }
            assert "134217728" in inspect(connection).get_check_constraints("koinon_bulk_items")[0][
                "sqltext"
            ] or any(
                "134217728" in item["sqltext"]
                for item in inspect(connection).get_check_constraints("koinon_bulk_items")
            )
            connection.exec_driver_sql("UPDATE koinon_bulk_uploads SET object_reference_json='{}'")
            with pytest.raises(RuntimeError, match="Retained large-file"):
                migration.downgrade()
    engine.dispose()
