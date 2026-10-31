# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


def load(path):
    assert path.is_file(), "A durable query feature requires additive native migrations"
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_query_additive_migrations_match_entities_and_keep_retained_rows(tmp_path):
    from koinon.knowledge.bulk_queries.entities import QueryBatch, QueryBatchItem, QueryBatchReference
    from koinon.knowledge.bulk_queries.native_entities import NativeQueryOperation

    root = Path(__file__).resolve().parents[4]
    primary = load(root / "deploy/migrations/native_versions/0028_bulk_queries.py")
    native = load(root / "packages/structured/migrations/koinon_versions/0020_bulk_query_operations.py")
    assert primary.down_revision == "koinon_0027_bulk_reservations"
    assert native.down_revision == "0019_consumer_context"
    assert max(len(primary.revision), len(native.revision)) <= 32
    engine = create_engine("sqlite:///" + str(tmp_path / "migrations.db"))
    with engine.begin() as connection:
        for name in [
            "lattice_tenants",
            "lattice_catalog",
            "lattice_jobs",
            "flyquery_datasets",
            "flyquery_queries",
        ]:
            connection.exec_driver_sql(f"CREATE TABLE {name} (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES ('retained')")
        with Operations.context(MigrationContext.configure(connection)):
            primary.upgrade()
            native.upgrade()
        actual = inspect(connection)
        for entity in [QueryBatch, QueryBatchItem, QueryBatchReference, NativeQueryOperation]:
            table = entity.__table__
            columns = {column["name"]: column for column in actual.get_columns(table.name)}
            assert set(columns) == set(table.columns.keys())
            for column in table.columns:
                assert columns[column.name]["nullable"] == column.nullable
                assert str(columns[column.name]["type"]) == str(
                    column.type.compile(dialect=connection.dialect)
                )
        assert connection.exec_driver_sql("SELECT * FROM lattice_tenants").all() == [("retained",)]
        connection.exec_driver_sql(
            "INSERT INTO flyquery_bulk_query_operations VALUES "
            "('id','retained','owner','workspace','dataset','workspace','dataset','Question',"
            "'policy','connections','admitted',NULL,NULL,'2026-10-30')"
        )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("UPDATE flyquery_bulk_query_operations SET question='Different'")
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("DELETE FROM flyquery_bulk_query_operations")
    engine.dispose()


def test_query_runtime_grants_are_narrow_and_never_delete():
    roles = load(Path(__file__).resolve().parents[4] / "deploy/provision_roles.py")

    class Recorder:
        def __init__(self):
            self.calls = []

        def execute(self, statement):
            self.calls.append(statement.as_string())

    for table, privileges in [
        ("koinon_query_batches", "SELECT,INSERT,UPDATE"),
        ("koinon_query_batch_items", "SELECT,INSERT,UPDATE"),
        ("koinon_query_batch_references", "SELECT,INSERT"),
        ("flyquery_bulk_query_operations", "SELECT,INSERT,UPDATE"),
    ]:
        record = Recorder()
        roles.grant_table(record, table, "inert")
        assert record.calls[0].startswith("REVOKE ALL")
        assert record.calls[1].startswith("GRANT " + privileges + " ON")
        assert "DELETE" not in record.calls[1]
