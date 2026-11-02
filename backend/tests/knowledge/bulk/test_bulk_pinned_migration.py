# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""SQLite and PostgreSQL pin validation share the native StoredObjectReference contract."""

import json

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from koinon_storage.files import StoredObjectReference
from sqlalchemy import create_engine
from sqlalchemy.exc import DBAPIError
from test_large_file_migration import load


def reference():
    return StoredObjectReference("original", 8, "a" * 64, "b" * 64, "azure_etag", '"etag"').to_dict()


def invalid_references(value=None):
    value = reference() if value is None else value
    for field, replacement in (
        ("schema_version", True),
        ("schema_version", 2),
        ("schema_version", "1"),
        ("key", "other"),
        ("size_bytes", 9),
        ("size_bytes", True),
        ("size_bytes", 8.0),
        ("sha256", "c" * 64),
        ("store_identity", "B" * 64),
        ("version_kind", "unversioned"),
        ("version", ""),
        ("version", "x" * 2049),
        ("version", "bad\nversion"),
        ("version", 4),
    ):
        yield {**value, field: replacement}
    yield {key: item for key, item in value.items() if key != "version"}
    yield {**value, "unexpected": "field"}
    yield {}
    yield []
    yield "not-an-object"
    yield False


@pytest.fixture
def migrated(tmp_path, request):
    engine = create_engine("sqlite:///" + str(tmp_path / "pins.db"))
    with engine.begin() as connection:
        for table in ("lattice_tenants", "lattice_catalog", "lattice_jobs", "koinon_external_file_reviews"):
            connection.exec_driver_sql(f"CREATE TABLE {table}(id VARCHAR(64) PRIMARY KEY)")
        with Operations.context(MigrationContext.configure(connection)):
            load("0024_bulk_intake.py").upgrade()
            load("0032_large_files.py").upgrade()
        connection.exec_driver_sql(
            "INSERT INTO koinon_bulk_items "
            "(id,batch_id,ordinal,client_item_id,filename,mode,size_bytes,sha256,"
            "source_id,asset_id,status,connection_json) "
            "VALUES ('item','batch',0,'client','facts.md','document',8,?,"
            "'source','asset','awaiting_upload','{}')",
            ("a" * 64,),
        )
        connection.exec_driver_sql(
            "INSERT INTO koinon_bulk_uploads "
            "(id,item_id,key_hash,object_key,status,permit_held,created_at) "
            "VALUES ('upload','item','key','original','uploading',1,CURRENT_TIMESTAMP)"
        )
        if getattr(request, "param", None) is not None:
            connection.exec_driver_sql(
                "UPDATE koinon_bulk_uploads SET object_reference_json=?", (json.dumps(request.param),)
            )
        before = connection.exec_driver_sql("SELECT * FROM koinon_bulk_uploads").one()
        with Operations.context(MigrationContext.configure(connection)):
            migration = load("0040_bulk_pinned_receipts.py")
            assert migration.down_revision == "koinon_0039_answer_release"
            assert len(migration.revision) <= 32
            migration.upgrade()
        assert connection.exec_driver_sql("SELECT * FROM koinon_bulk_uploads").one() == before
    yield engine
    engine.dispose()


def test_sqlite_first_pin_is_validated_then_semantically_immutable(migrated):
    with migrated.begin() as connection:
        for invalid in invalid_references():
            with pytest.raises(DBAPIError):
                connection.exec_driver_sql(
                    "UPDATE koinon_bulk_uploads SET object_reference_json=?", (json.dumps(invalid),)
                )
        value = reference()
        connection.exec_driver_sql(
            "UPDATE koinon_bulk_uploads SET object_reference_json=?,status='verified',permit_held=0",
            (json.dumps(value),),
        )
        connection.exec_driver_sql(
            "UPDATE koinon_bulk_uploads SET object_reference_json=?",
            (json.dumps(dict(reversed(list(value.items())))),),
        )
        for changed in (None, "null", json.dumps({**value, "version": "other"}), "{}"):
            with pytest.raises(DBAPIError):
                connection.exec_driver_sql(
                    "UPDATE koinon_bulk_uploads SET object_reference_json=?", (changed,)
                )
        for assignment in ("object_key='other'", "permit_held=1", "status='uploading'"):
            with pytest.raises(DBAPIError):
                connection.exec_driver_sql("UPDATE koinon_bulk_uploads SET " + assignment)
        with pytest.raises(DBAPIError):
            connection.exec_driver_sql("DELETE FROM koinon_bulk_uploads")
        assert (
            json.loads(
                connection.exec_driver_sql(
                    "SELECT object_reference_json FROM koinon_bulk_uploads"
                ).scalar_one()
            )
            == value
        )


def test_sqlite_null_sentinel_and_temp_manifest_cannot_bypass_first_pin(migrated):
    with migrated.begin() as connection:
        connection.exec_driver_sql("UPDATE koinon_bulk_uploads SET object_reference_json='null'")
        connection.exec_driver_sql(
            "CREATE TEMP TABLE koinon_bulk_items(id TEXT,sha256 TEXT,size_bytes INTEGER)"
        )
        connection.exec_driver_sql("INSERT INTO temp.koinon_bulk_items VALUES ('item',?,9)", ("c" * 64,))
        with pytest.raises(DBAPIError):
            connection.exec_driver_sql(
                "UPDATE main.koinon_bulk_uploads SET object_reference_json=?",
                (json.dumps({**reference(), "sha256": "c" * 64, "size_bytes": 9}),),
            )
        connection.exec_driver_sql(
            "UPDATE main.koinon_bulk_uploads SET object_reference_json=?", (json.dumps(reference()),)
        )


def test_sqlite_insert_cannot_bypass_pin_validation(migrated):
    with migrated.begin() as connection, pytest.raises(DBAPIError):
        connection.exec_driver_sql(
            "INSERT INTO koinon_bulk_uploads "
            "(id,item_id,key_hash,object_key,status,permit_held,created_at,object_reference_json) "
            "VALUES ('other','item','other','unmatched','verified',0,CURRENT_TIMESTAMP,?)",
            (json.dumps(reference()),),
        )


@pytest.mark.parametrize("migrated", [reference()], indirect=True)
def test_sqlite_retained_nonnull_pin_is_not_rewritten_or_rebound_by_upgrade(migrated):
    with migrated.begin() as connection:
        assert (
            json.loads(
                connection.exec_driver_sql(
                    "SELECT object_reference_json FROM koinon_bulk_uploads"
                ).scalar_one()
            )
            == reference()
        )
        with pytest.raises(DBAPIError):
            connection.exec_driver_sql("UPDATE koinon_bulk_uploads SET object_reference_json=NULL")
        with pytest.raises(DBAPIError):
            connection.exec_driver_sql(
                "UPDATE koinon_bulk_uploads SET object_reference_json=?",
                (json.dumps({**reference(), "version": "changed"}),),
            )
