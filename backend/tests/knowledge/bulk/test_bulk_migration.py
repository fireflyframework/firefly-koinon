# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError

from koinon.knowledge.bulk.entities import BulkBatch, BulkItem, BulkQuota, BulkUpload


def test_additive_bulk_migration_metadata_and_immutable_receipts_preserve_retained_rows(tmp_path):
    path = Path(__file__).resolve().parents[4] / "deploy/migrations/native_versions/0024_bulk_intake.py"
    assert path.is_file(), "Durable bulk requires its own additive migration"
    spec = importlib.util.spec_from_file_location("bulk24", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.revision == "koinon_0024_bulk" and migration.down_revision == "koinon_0023_ciam_profiles"
    assert len(migration.revision) <= 32
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES ('retained')")
        connection.exec_driver_sql("CREATE TABLE lattice_catalog (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE lattice_jobs (id VARCHAR(64) PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        actual = inspect(connection)
        for entity in [BulkBatch, BulkItem, BulkUpload, BulkQuota]:
            table = entity.__table__
            columns = {c["name"]: c for c in actual.get_columns(table.name)}
            expected = set(table.columns.keys()) - (
                {"reservation_json"}
                if entity is BulkItem
                else {"object_reference_json"}
                if entity is BulkUpload
                else set()
            )
            assert set(columns) == expected
            for column in table.columns:
                if column.name in {"reservation_json", "object_reference_json"}:
                    continue  # Added by the separately tested additive 0026 migration.
                assert columns[column.name]["nullable"] == column.nullable
                assert str(columns[column.name]["type"]) == str(
                    column.type.compile(dialect=connection.dialect)
                )
            assert {i["name"] for i in actual.get_indexes(table.name)} == {i.name for i in table.indexes}
            assert {c["name"] for c in actual.get_check_constraints(table.name)} == {
                c.name for c in table.constraints if c.__class__.__name__ == "CheckConstraint"
            }
        connection.exec_driver_sql("INSERT INTO koinon_bulk_quotas VALUES ('tenant:retained',8,1)")
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("UPDATE koinon_bulk_quotas SET reserved_bytes=0")
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql("DELETE FROM koinon_bulk_quotas")
        assert connection.exec_driver_sql("SELECT * FROM lattice_tenants").all() == [("retained",)]
    engine.dispose()


def test_bulk_runtime_grants_never_allow_deletion():
    path = Path(__file__).resolve().parents[4] / "deploy/provision_roles.py"
    spec = importlib.util.spec_from_file_location("bulk_roles", path)
    roles = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(roles)

    class Recorder:
        def __init__(self):
            self.calls = []

        def execute(self, statement):
            self.calls.append(statement.as_string())

    for table in [
        BulkBatch.__tablename__,
        BulkItem.__tablename__,
        BulkUpload.__tablename__,
        BulkQuota.__tablename__,
    ]:
        recorder = Recorder()
        roles.grant_table(recorder, table, "inert_primary")
        assert len(recorder.calls) == 2 and recorder.calls[0].startswith("REVOKE ALL")
        assert recorder.calls[1].startswith("GRANT SELECT,INSERT,UPDATE ON")
        assert "DELETE" not in recorder.calls[1]


def test_native_dataset_reservations_have_only_their_narrow_table_privileges():
    path = Path(__file__).resolve().parents[4] / "deploy/provision_roles.py"
    spec = importlib.util.spec_from_file_location("bulk_dataset_roles", path)
    roles = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(roles)

    class Recorder:
        def __init__(self):
            self.calls = []

        def execute(self, statement):
            self.calls.append(statement.as_string())

    for table, allowed in [
        ("koinon_bulk_table_reservations", "SELECT,INSERT"),
        ("flyquery_bulk_operations", "SELECT,INSERT,UPDATE"),
    ]:
        recorder = Recorder()
        roles.grant_table(recorder, table, "inert_runtime")
        assert len(recorder.calls) == 2 and recorder.calls[0].startswith("REVOKE ALL")
        assert recorder.calls[1].startswith("GRANT " + allowed + " ON")
        assert "DELETE" not in recorder.calls[1]
