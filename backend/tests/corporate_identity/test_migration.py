# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from koinon.corporate_identity.entities import (
    CorporateGrant,
    CorporateMapping,
    CorporateProvider,
    CorporateValidation,
)


def test_exact_0011_migration_matches_owned_entity_columns_and_indexes_without_changing_memberships(tmp_path):
    path = (
        Path(__file__).resolve().parents[3] / "deploy/migrations/native_versions/0011_corporate_identity.py"
    )
    spec = importlib.util.spec_from_file_location("identity_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "koinon_0011_corporate_identity"
    assert module.down_revision == "koinon_0010_knowledge_indexes"
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_memberships (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO lattice_memberships (id) VALUES ('preserved')")
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        view = inspect(connection)
        for entity in (CorporateProvider, CorporateMapping, CorporateGrant, CorporateValidation):
            table = entity.__table__
            columns = {column["name"]: column for column in view.get_columns(table.name)}
            assert set(columns) == set(table.columns.keys())
            assert all(columns[column.name]["nullable"] == column.nullable for column in table.columns)
            assert {index["name"] for index in view.get_indexes(table.name)} == {
                index.name for index in table.indexes
            }
        assert connection.exec_driver_sql("SELECT id FROM lattice_memberships").all() == [("preserved",)]
    engine.dispose()
