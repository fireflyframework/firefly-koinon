# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from koinon.knowledge.bulk.structured_entities import StructuredBulkOperation


def test_structured_bulk_receipt_is_additive_metadata_exact_and_immutable_after_assignment():
    path = (
        Path(__file__).resolve().parents[4]
        / "packages/structured/migrations/koinon_versions/0018_bulk_operations.py"
    )
    assert path.is_file()
    spec = importlib.util.spec_from_file_location("structured18", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert (
        migration.revision == "0018_bulk_operations"
        and migration.down_revision == "0017_snapshot_coordinates"
    )
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE flyquery_datasets (id CHAR(32) PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO flyquery_datasets VALUES ('retained')")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        columns = {c["name"]: c for c in inspect(connection).get_columns("flyquery_bulk_operations")}
        assert set(columns) == set(StructuredBulkOperation.__table__.columns.keys())
        assert all(
            columns[c.name]["nullable"] == c.nullable for c in StructuredBulkOperation.__table__.columns
        )
        connection.exec_driver_sql(
            "INSERT INTO flyquery_bulk_operations "
            "(id,tenant_id,workspace_id,dataset_id,file_id,actor,"
            "catalog_source_id,catalog_dataset_id,"
            "catalog_file_version_id,filename,sha256,size_bytes,status,created_at) "
            "VALUES ('op','north','workspace','dataset','file','owner',"
            "'source','asset','version','facts.csv',"
            "'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
            "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',8,'admitted',CURRENT_TIMESTAMP)"
        )
        connection.exec_driver_sql("UPDATE flyquery_bulk_operations SET plan_json='[{}]' WHERE id='op'")
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("UPDATE flyquery_bulk_operations SET plan_json=NULL")
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("UPDATE flyquery_bulk_operations SET tenant_id='south'")
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "UPDATE flyquery_bulk_operations SET status='committed',receipt_json='{}'"
            )
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("DELETE FROM flyquery_bulk_operations")
        assert connection.exec_driver_sql("SELECT id FROM flyquery_datasets").all() == [("retained",)]
    engine.dispose()
