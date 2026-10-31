# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


def test_reservation_extension_adds_one_nullable_immutable_column_without_rewriting_old_rows():
    path = Path(__file__).resolve().parents[4] / "deploy/migrations/native_versions/0027_bulk_reservations.py"
    assert path.is_file()
    spec = importlib.util.spec_from_file_location("bulk26", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "koinon_0027_bulk_reservations"
    assert migration.down_revision == "koinon_0026_mcp_sessions" and len(migration.revision) <= 32
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE koinon_bulk_items (id TEXT PRIMARY KEY, status TEXT)")
        connection.exec_driver_sql("INSERT INTO koinon_bulk_items VALUES ('retained','succeeded')")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = {c["name"]: c for c in inspect(connection).get_columns("koinon_bulk_items")}
        assert (
            set(columns) == {"id", "status", "reservation_json"} and columns["reservation_json"]["nullable"]
        )
        assert connection.exec_driver_sql("SELECT * FROM koinon_bulk_items").all() == [
            ("retained", "succeeded", None)
        ]
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "UPDATE koinon_bulk_items SET reservation_json='{}' WHERE id='retained'"
            )
        connection.exec_driver_sql(
            "INSERT INTO koinon_bulk_items VALUES ('new','queued','{\"native_file_id\":\"reserved\"}')"
        )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("UPDATE koinon_bulk_items SET reservation_json=NULL WHERE id='new'")
    engine.dispose()


def test_reserved_table_catalog_identity_is_durable_unique_and_immutable():
    path = Path(__file__).resolve().parents[4] / "deploy/migrations/native_versions/0027_bulk_reservations.py"
    spec = importlib.util.spec_from_file_location("bulk26_tables", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE koinon_bulk_items (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE lattice_catalog (id TEXT PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        connection.exec_driver_sql("INSERT INTO koinon_bulk_items(id) VALUES ('item')")
        connection.exec_driver_sql("INSERT INTO lattice_catalog VALUES ('catalog')")
        connection.exec_driver_sql(
            "INSERT INTO koinon_bulk_table_reservations VALUES ('item',0,'table',"
            "'snapshot','catalog','facts')"
        )
        for statement in [
            "UPDATE koinon_bulk_table_reservations SET name='replacement'",
            "DELETE FROM koinon_bulk_table_reservations",
            "INSERT INTO koinon_bulk_table_reservations VALUES ('item',16,'other','other','other','other')",
            "INSERT INTO koinon_bulk_table_reservations VALUES ('item',1,'table','new','new','new')",
        ]:
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(statement)
        assert connection.exec_driver_sql("SELECT name FROM koinon_bulk_table_reservations").all() == [
            ("facts",)
        ]
    engine.dispose()
