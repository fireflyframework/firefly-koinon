# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect

from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot, KnowledgeIntentRow


def test_fixed_primary_0014_matches_entities_and_preserves_existing_catalog(tmp_path):
    path = Path(__file__).resolve().parents[3] / "deploy/migrations/native_versions/0014_curated_knowledge.py"
    spec = importlib.util.spec_from_file_location("curated_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "koinon_0014_curated_knowledge"
    assert module.down_revision == "koinon_0013_exports_shares" and len(module.revision) <= 32
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_catalog (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO lattice_catalog (id) VALUES ('retained')")
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        view = inspect(connection)
        for entity in (KnowledgeIntentRow, CuratedCatalogState, CuratedSourceRoot):
            table = entity.__table__
            columns = {column["name"]: column for column in view.get_columns(table.name)}
            assert set(columns) == set(table.columns.keys())
            assert all(columns[column.name]["nullable"] == column.nullable for column in table.columns)
            assert {index["name"] for index in view.get_indexes(table.name)} == {
                index.name for index in table.indexes
            }
        assert connection.exec_driver_sql("SELECT id FROM lattice_catalog").all() == [("retained",)]
    engine.dispose()
