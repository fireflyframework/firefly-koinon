# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact replacement producers and metadata-only query acknowledgements."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from psycopg.types.json import Json
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import source_database as source_database

pytestmark = pytest.mark.integration


def replacement_producer(connection, *, audited=True):
    initial = {
        "domain": "canon",
        "native_workspace_id": "native-space",
        "native_source_id": "native-source",
        "native_asset_id": "native-asset",
        "source_version_id": "old-version",
        "extraction_id": "old-extraction",
        "sha256": "d" * 64,
        "size_bytes": 7,
    }
    connection.execute(
        """INSERT INTO koinon_content_imports
        (id,tenant_id,mapping_id,mapping_revision,object_id,generation,intake_item_id,provider,external_subject,
         drive_id,remote_item_id,remote_version,source_id,asset_id,sha256,size_bytes,receipt_json,created_at,committed_at)
        VALUES('initial','retained','mapping',1,'origin',1,'item','google_drive','provider-alice',
         'drive','remote-file','v1','source','asset',repeat('d',64),7,%s,now(),now())""",
        (Json(initial),),
    )
    connection.execute(
        "INSERT INTO koinon_content_imported_assets VALUES('asset','retained','source','initial',now())"
    )
    connection.execute("UPDATE koinon_content_objects SET generation=2,remote_version='v2' WHERE id='origin'")
    operation = str(uuid4())
    metadata = {
        "operation": "document.reingest",
        "sha256": "e" * 64,
        "bytes": 8,
        "_koinon_processing": {"operation": "document.reingest", "state": "unknown"},
    }
    connection.execute(
        """INSERT INTO
lattice_catalog(id,tenant_id,workspace_id,project_id,parent_id,kind,name,description,status,
        metadata_json,created_by,updated_by,created_at,updated_at)
        VALUES(%s,'retained','workspace','project','source','index_version','private.docx','','pending',%s,
        'issuer|alice','issuer|alice',now(),now())""",
        (operation, Json(metadata)),
    )
    if audited:
        connection.execute(
            "INSERT INTO "
            "lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
            "VALUES(%s,'retained','issuer|alice','knowledge.content.recorded',%s,%s,now())",
            (str(uuid4()), operation, Json({"operation": "document.reingest", "state": "unknown"})),
        )
    return operation, initial


def replacement_attempt(connection, operation, *, intake=None):
    connection.execute(
        """INSERT INTO koinon_content_imports
        (id,tenant_id,mapping_id,mapping_revision,object_id,generation,intake_item_id,content_operation_id,provider,
         external_subject,drive_id,remote_item_id,remote_version,source_id,asset_id,sha256,size_bytes,created_at)
        VALUES('replacement','retained','mapping',1,'origin',2,%s,%s,'google_drive','provider-alice',
        'drive','remote-file','v2','source','asset',repeat('e',64),8,now())""",
        (intake, operation),
    )


async def test_replacement_preserves_identity_and_binds_exact_native_receipt(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        operation, initial = replacement_producer(connection)
        replacement_attempt(connection, operation)
        receipt = {
            **initial,
            "operation_id": operation,
            "sha256": "e" * 64,
            "size_bytes": 8,
            "source_version_id": "new-version",
            "extraction_id": "new-extraction",
        }
        for change in (
            {"operation_id": str(uuid4())},
            {"native_source_id": "foreign"},
            {"sha256": "f" * 64},
            {"extraction_id": None},
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE "
                    "id='replacement'",
                    (Json({**receipt, **change}),),
                )
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='replacement'",
            (Json(receipt),),
        )
        connection.commit()
        assert connection.execute(
            "SELECT source_id,asset_id,intake_item_id,content_operation_id FROM "
            "koinon_content_imports WHERE id='replacement'"
        ).fetchone() == ("source", "asset", None, operation)
        assert connection.execute(
            "SELECT count(*) FROM lattice_catalog WHERE kind='document'"
        ).fetchone() == (1,)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("UPDATE koinon_content_imports SET remote_version='v3' WHERE id='replacement'")


@pytest.mark.parametrize(
    "problem", ["no_audit", "both_producers", "no_producer", "wrong_owner", "wrong_parent", "wrong_hash"]
)
async def test_catalog_metadata_cannot_forge_replacement_origin(source_sessions, problem):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        operation, _ = replacement_producer(connection, audited=problem != "no_audit")
        if problem == "wrong_owner":
            connection.execute("UPDATE lattice_catalog SET created_by='other' WHERE id=%s", (operation,))
        elif problem == "wrong_parent":
            connection.execute("UPDATE lattice_catalog SET parent_id='folder' WHERE id=%s", (operation,))
        elif problem == "wrong_hash":
            connection.execute(
                "UPDATE lattice_catalog SET "
                "metadata_json=jsonb_set(metadata_json::jsonb,'{sha256}','\"forged\"') WHERE "
                "id=%s",
                (operation,),
            )
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            replacement_attempt(
                connection,
                None if problem == "no_producer" else operation,
                intake="item" if problem == "both_producers" else None,
            )
        assert connection.execute(
            "SELECT count(*) FROM koinon_content_imports WHERE id='replacement'"
        ).fetchone() == (0,)


def query_item(engine):
    from koinon.jobs.entities import Job
    from koinon.knowledge.bulk_queries.entities import QueryBatch, QueryBatchItem

    identifier, batch, job = map(str, (uuid4(), uuid4(), uuid4()))
    with engine.begin() as connection:
        connection.execute(
            Job.__table__.insert().values(
                id=job,
                tenant_id="retained",
                resource_id="asset",
                kind="knowledge.query",
                idempotency_key=job,
                payload_hash="a" * 64,
            )
        )
        connection.execute(
            QueryBatch.__table__.insert().values(
                id=batch,
                tenant_id="retained",
                workspace_id="workspace",
                subject="issuer|alice",
                key_hash="b" * 64,
                request_hash="c" * 64,
                request_json={},
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
        connection.execute(
            QueryBatchItem.__table__.insert().values(
                id=identifier,
                batch_id=batch,
                ordinal=0,
                client_item_id="one",
                dataset_id="asset",
                question="Question",
                native_workspace_id="native-workspace",
                native_dataset_id="native-dataset",
                connection_json={},
                policy_json={},
                job_id=job,
            )
        )
    return identifier


def descriptor(identifier):
    return {
        "schema": "koinon.native-query-commit.v1",
        "operation_id": identifier,
        "query_id": str(uuid4()),
        "identity_sha256": "a" * 64,
        "receipt_sha256": "b" * 64,
        "manifest_sha256": "c" * 64,
        "outcome": "succeeded",
    }


async def test_query_can_acknowledge_metadata_without_materializing_result(source_sessions, source_database):
    _, uri = source_sessions
    identifier = query_item(source_database[2])
    value = descriptor(identifier)
    with psycopg.connect(uri) as connection:
        connection.execute(
            "UPDATE koinon_query_batch_items SET status='succeeded',native_commit_json=%s WHERE id=%s",
            (Json(value), identifier),
        )
        connection.commit()
        assert connection.execute(
            "SELECT status,result_json FROM koinon_query_batch_items WHERE id=%s", (identifier,)
        ).fetchone() == ("succeeded", None)
        assert connection.execute("SELECT count(*) FROM koinon_query_batch_references").fetchone() == (0,)
        for changed in (None, {**value, "query_id": str(uuid4())}):
            with pytest.raises(psycopg.Error), connection.transaction():
                connection.execute(
                    "UPDATE koinon_query_batch_items SET native_commit_json=%s WHERE id=%s",
                    (Json(changed) if changed else None, identifier),
                )


@pytest.mark.parametrize(
    "change",
    [
        {"operation_id": str(uuid4())},
        {"query_id": "wrong"},
        {"manifest_sha256": None},
        {"outcome": "failed"},
        {"preview": "protected"},
        {"schema": None},
    ],
)
async def test_query_descriptor_rejects_wrong_identity_and_protected_payload(
    source_sessions, source_database, change
):
    _, uri = source_sessions
    identifier = query_item(source_database[2])
    with psycopg.connect(uri) as connection:
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "UPDATE koinon_query_batch_items SET status='succeeded',native_commit_json=%s WHERE id=%s",
                (Json({**descriptor(identifier), **change}), identifier),
            )
        assert connection.execute(
            "SELECT status,native_commit_json FROM koinon_query_batch_items WHERE id=%s", (identifier,)
        ).fetchone() == ("queued", None)


async def test_recorded_producer_lookup_uses_partial_index(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO "
            "lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
            "SELECT "
            "'audit-'||n,'retained','issuer|alice','knowledge.content.recorded','operation-"
            "'||n,'{}',now() FROM generate_series(1,10000) n"
        )
        connection.execute("ANALYZE lattice_audit")
        plan = connection.execute(
            "EXPLAIN(ANALYZE,FORMAT JSON) SELECT id FROM lattice_audit WHERE "
            "tenant_id='retained' AND subject='issuer|alice' AND "
            "action='knowledge.content.recorded' AND resource_id='operation-9999'"
        ).fetchone()[0][0]["Plan"]
        assert plan["Actual Rows"] == 1
        assert plan["Index Name"] == "ix_content_producer_audit"


def test_primary_recovery_retry_keeps_concurrent_index_and_rolls_back_expansion(source_database):
    from alembic import command
    from sqlalchemy import event
    from test_source_migration_postgres import ROOT, load

    target, _, engine = source_database
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    migrate = load("deploy/migrate.py")
    versions = ROOT / "deploy/migrations/native_versions"
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("native", versions, connection), "koinon_0047_source_controls")
        connection.commit()

    def interrupt(connection, cursor, statement, parameters, context, executemany):
        if "CREATE FUNCTION public.koinon_policy_receipt_guard" in statement:
            raise RuntimeError("owned primary migration interruption")

    with engine.connect() as connection:
        event.listen(connection, "before_cursor_execute", interrupt)
        try:
            with pytest.raises(RuntimeError, match="owned primary migration interruption"):
                command.upgrade(
                    migrate.history_config("native", versions, connection), "koinon_0048_source_recovery"
                )
        finally:
            event.remove(connection, "before_cursor_execute", interrupt)
            connection.rollback()
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT version_num FROM koinon_native_version").fetchone() == (
            "koinon_0047_source_controls",
        )
        assert connection.execute("SELECT to_regclass('koinon_content_policy_operations')").fetchone() == (
            None,
        )
        assert connection.execute(
            "SELECT indisvalid FROM pg_index WHERE indexrelid='ix_content_producer_audit'::regclass"
        ).fetchone() == (True,)
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("native", versions, connection), "koinon_0048_source_recovery")
        connection.commit()
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT version_num FROM koinon_native_version").fetchone() == (
            "koinon_0048_source_recovery",
        )
        assert connection.execute("SELECT name FROM lattice_tenants WHERE id='retained'").fetchone() == (
            "Retained",
        )
