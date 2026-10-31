# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Additive lease state cannot weaken retained bulk identities and receipts."""

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError


def test_additive_staging_guards_fence_tokens_and_retain_completed_recovery_receipts(tmp_path):
    root = Path(__file__).resolve().parents[4]
    paths = list((root / "deploy/migrations/native_versions").glob("*_bulk_staging.py"))
    assert len(paths) == 1, "Portable staging needs a separate additive migration"
    spec = importlib.util.spec_from_file_location("bulk_staging", paths[0])
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine("sqlite:///" + str(tmp_path / "leases.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE koinon_bulk_uploads(id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE koinon_bulk_batches(id VARCHAR(64) PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade()
        connection.exec_driver_sql(
            "INSERT INTO koinon_bulk_upload_states VALUES "
            "('upload',1,'owner','writing','2030-01-01','store',NULL)"
        )
        for assignment in (
            "generation=0",
            "owner_hash='other'",
            "storage_identity='other'",
            "lease_until='2031-01-01'",
            "operation='verifying'",
        ):
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql("UPDATE koinon_bulk_upload_states SET " + assignment)
        connection.exec_driver_sql(
            "UPDATE koinon_bulk_upload_states SET generation=2, "
            "owner_hash='verifier',operation='verifying',recovery_id='recovery'"
        )
        connection.exec_driver_sql(
            "INSERT INTO koinon_bulk_recoveries VALUES "
            "('recovery','batch','upload','key','request',2,2,'verifier','2030-01-01',1,0)"
        )
        connection.exec_driver_sql("UPDATE koinon_bulk_upload_states SET operation='closed'")
        connection.exec_driver_sql("UPDATE koinon_bulk_recoveries SET permit_held=0,completed=1")
        for table, assignment in (
            ("koinon_bulk_upload_states", "generation=3,operation='writing'"),
            ("koinon_bulk_recoveries", "completed=0"),
            ("koinon_bulk_recoveries", "request_hash='other'"),
            ("koinon_bulk_recoveries", "permit_held=1"),
        ):
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(f"UPDATE {table} SET {assignment}")
        for table in ("koinon_bulk_upload_states", "koinon_bulk_recoveries"):
            with pytest.raises(IntegrityError):
                connection.exec_driver_sql(f"DELETE FROM {table}")
    engine.dispose()
