# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import inspect
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from koinon.communications import entities


def test_communications_migration_retains_originals_and_matches_frozen_native_tables():
    path = (
        Path(__file__).parents[1] / "migrations/native_versions/0030_communications.py"
    )
    spec = importlib.util.spec_from_file_location("communications_upgrade", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "koinon_0030_comms"
    assert migration.down_revision == "koinon_0029_bulk_staging"
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE retained_original (id TEXT PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO retained_original VALUES ('same-preserved-data')"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert (
                connection.exec_driver_sql("SELECT id FROM retained_original").scalar()
                == "same-preserved-data"
            )
            inspector = sa.inspect(connection)
            tables = [
                value.__table__
                for value in vars(entities).values()
                if inspect.isclass(value)
                and value.__module__ == entities.__name__
                and hasattr(value, "__table__")
                and value is not entities.BootstrapContactRecord
            ]
            assert len(tables) == 9
            for table in tables:
                actual = {
                    column["name"]: column
                    for column in inspector.get_columns(table.name)
                }
                assert set(actual) == {column.name for column in table.columns}
                for column in table.columns:
                    assert actual[column.name]["nullable"] == column.nullable
                assert {
                    index["name"] for index in inspector.get_indexes(table.name)
                } == {index.name for index in table.indexes}
    finally:
        engine.dispose()
