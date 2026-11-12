# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Durable source publication evidence against an isolated real PostgreSQL database."""

import asyncio
import copy
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_concurrency_postgres import wait_for_blocked_connection
from test_source_migration_postgres import ROOT, load, upgrade_sources
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import job_and_run, policy, work_and_observation

pytestmark = pytest.mark.integration

native_schema = load("backend/tests/knowledge/test_metadata_provenance_schema.py")
metadata_database = native_schema.metadata_database


def reserve_document(connection, *, fresh=True, dataset=False, reservation=None):
    policy(connection)
    job_and_run(connection, "first")
    work_and_observation(connection)
    connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=1 WHERE id='first'")
    source, asset, item = (
        ("fresh-source", "fresh-asset", "fresh-item") if fresh else ("source", "asset", "item")
    )
    if fresh:
        for original, identifier, parent in (("source", source, "folder"), ("asset", asset, source)):
            connection.execute(
                "INSERT INTO lattice_catalog SELECT (jsonb_populate_record(NULL::lattice_catalog,"
                "to_jsonb(c)||%s::jsonb)).* FROM lattice_catalog c WHERE id=%s",
                (
                    Jsonb(
                        {
                            "id": identifier,
                            "parent_id": parent,
                            "status": "pending",
                            **({"kind": "dataset"} if dataset and original == "asset" else {}),
                        }
                    ),
                    original,
                ),
            )
        connection.execute(
            "INSERT INTO koinon_bulk_items SELECT (jsonb_populate_record(NULL::koinon_bulk_items,"
            "to_jsonb(i)||%s::jsonb)).* FROM koinon_bulk_items i WHERE id='item'",
            (
                Jsonb(
                    {
                        "id": item,
                        "ordinal": 1,
                        "client_item_id": "fresh",
                        "source_id": source,
                        "asset_id": asset,
                        "mode": "dataset" if dataset else "document",
                        "reservation_json": reservation,
                    }
                ),
            ),
        )
    else:
        connection.execute("UPDATE lattice_catalog SET status='pending' WHERE id IN ('source','asset')")
    connection.execute(
        "INSERT INTO koinon_content_imports(id,tenant_id,mapping_id,mapping_revision,object_id,generation,"
        "intake_item_id,provider,external_subject,drive_id,remote_item_id,remote_version,source_id,asset_id,sha256,size_bytes,created_at)"
        " "
        "VALUES('attempt','retained','mapping',1,'origin',1,%s,'google_drive','provider-alice','drive','remote-file','v1',%s,%s,%s,7,now())",
        (item, source, asset, "d" * 64),
    )
    connection.execute("UPDATE koinon_content_sync_work SET attempt_id='attempt' WHERE id='work'")
    connection.execute(
        "INSERT INTO "
        "koinon_content_publication_baselines(attempt_id,tenant_id,workspace_id,project_id,mapping_id,object_id,source_id,asset_id,producer_kind,created_at)"
        " "
        "VALUES('attempt','retained','workspace','project','mapping','origin',%s,%s,%s,now())",
        (source, asset, "initial_dataset" if dataset else "initial_document"),
    )
    return source, asset, item


def pin(connection, identifier, role, *, attempt="attempt"):
    connection.execute(
        "INSERT INTO "
        "koinon_content_publication_targets(attempt_id,catalog_id,tenant_id,workspace_id,project_id,role,disposition,parent_id,kind,mutation_revision,status)"
        " "
        "SELECT %s,id,tenant_id,workspace_id,project_id,%s,'add',parent_id,kind,mutation_revision,status "
        "FROM lattice_catalog WHERE id=%s",
        (attempt, role, identifier),
    )


def freeze(connection, transform=None, *, persist=True):
    header = connection.execute(
        "SELECT "
        "to_jsonb(h)-ARRAY['created_at','descriptor_json','descriptor_sha256','acknowledgement_json',"
        "'acknowledgement_sha256','previous_structure_publication_id']"
        " FROM koinon_content_publication_baselines h WHERE attempt_id='attempt'"
    ).fetchone()[0]
    pins = connection.execute(
        "SELECT to_jsonb(t)-'attempt_id' FROM koinon_content_publication_targets t WHERE "
        "attempt_id='attempt' ORDER BY catalog_id"
    ).fetchall()
    dataset = header["producer_kind"] == "initial_dataset"
    members = []
    if dataset:
        for ordinal, table_id, snapshot_id, catalog_table_id, name in connection.execute(
            "SELECT ordinal,table_id,snapshot_id,catalog_table_id,name FROM "
            "koinon_bulk_table_reservations WHERE item_id='fresh-item' ORDER BY ordinal"
        ):
            members.append(
                dict(
                    ordinal=ordinal,
                    table_id=table_id,
                    snapshot_id=snapshot_id,
                    catalog_table_id=catalog_table_id,
                    name=name,
                    member_key="member-" + str(ordinal),
                    parser_fingerprint="parser-v1",
                )
            )

    def binding(p):
        if not dataset:
            return {
                "domain": "canon",
                "native_workspace_id": {"receipt_field": "native_workspace_id"},
                "native_id": {
                    "receipt_field": "native_source_id" if p["role"] == "source" else "native_asset_id"
                },
                "native_version_id": {"receipt_field": "source_version_id"},
                "native_snapshot_id": {"receipt_field": "extraction_id"},
            }
        native_id = {"receipt_field": "native_source_id" if p["role"] == "source" else "native_asset_id"}
        version = snapshot = None
        if p["role"] == "new_index":
            native_id = version = {"receipt_field": "native_file_id"}
        elif p["role"] == "member":
            ordinal = next(m["ordinal"] for m in members if m["catalog_table_id"] == p["catalog_id"])
            native_id, version, snapshot = (
                {"receipt_field": f"tables.{ordinal}.table_id"},
                {"receipt_field": "native_file_id"},
                {"receipt_field": f"tables.{ordinal}.snapshot_id"},
            )
        return dict(
            domain="structured",
            native_workspace_id={"receipt_field": "native_workspace_id"},
            native_id=native_id,
            native_version_id=version,
            native_snapshot_id=snapshot,
        )

    descriptor = {
        "schema": "koinon.source-publication-descriptor.v1",
        "identity": {**header, "generation": 1, "mapping_revision": 1},
        "producer": {"intake_item_id": "fresh-item", "content_operation_id": None},
        "observation": {"run_id": "first", "work_id": "work", "observation_id": "observation"},
        "content": {"remote_version": "v1", "sha256": "d" * 64, "size_bytes": 7},
        "previous_acknowledgement_sha256": None,
        "native": {
            "domain": "structured" if dataset else "canon",
            "workspace_id": "native-space",
            "operation_id": "fresh-item" if dataset else "upload:fresh-source",
            "expected_heads": None,
        },
        "members": members,
        "targets": [
            {"pin": p, "writes": [{"action": "update", "fields": {"status": "ready"}}], "binding": binding(p)}
            for (p,) in pins
        ],
    }
    if transform is not None:
        transform(descriptor)
    if not persist:
        return descriptor, None
    digest = connection.execute(
        "UPDATE koinon_content_publication_baselines SET descriptor_json=%s WHERE "
        "attempt_id='attempt' RETURNING descriptor_sha256",
        (Jsonb(descriptor),),
    ).fetchone()[0]
    return descriptor, digest


def native_receipt(digest):
    return dict(
        domain="canon",
        native_workspace_id="native-space",
        native_source_id="native-source",
        native_asset_id="native-asset",
        sha256="d" * 64,
        size_bytes=7,
        source_version_id="version",
        extraction_id="extraction",
        n_chunks=1,
        object_key="private/key",
        file_version_id=None,
        native_file_id=None,
        tables=[],
        source_attempt_id="attempt",
        source_publication_sha256=digest,
    )


def reserve_dataset(connection, count):
    native_dataset, native_file = str(uuid4()), str(uuid4())
    reservation = dict(
        native_dataset_id=native_dataset,
        native_file_id=native_file,
        catalog_file_version_id="dataset-index",
        max_tables=16,
    )
    source, asset, _ = reserve_document(connection, dataset=True, reservation=reservation)
    connection.execute(
        "INSERT INTO lattice_catalog SELECT "
        "(jsonb_populate_record(NULL::lattice_catalog,to_jsonb(c)||%s::jsonb)).* FROM "
        "lattice_catalog c WHERE id='fresh-asset'",
        (
            Jsonb(
                {"id": "dataset-index", "kind": "index_version", "parent_id": asset, "mutation_revision": 1}
            ),
        ),
    )
    pin(connection, source, "source")
    pin(connection, asset, "asset")
    pin(connection, "dataset-index", "new_index")
    tables = []
    for ordinal in range(count):
        catalog, table, snapshot = f"dataset-member-{ordinal:02}", str(uuid4()), str(uuid4())
        connection.execute(
            "INSERT INTO lattice_catalog SELECT "
            "(jsonb_populate_record(NULL::lattice_catalog,to_jsonb(c)||%s::jsonb)).* FROM "
            "lattice_catalog c WHERE id='fresh-asset'",
            (
                Jsonb(
                    {
                        "id": catalog,
                        "kind": "table",
                        "parent_id": asset,
                        "name": f"Member {ordinal}",
                        "mutation_revision": 1,
                        "metadata_json": {"snapshot_id": snapshot},
                    }
                ),
            ),
        )
        connection.execute(
            "INSERT INTO "
            "koinon_bulk_table_reservations(item_id,ordinal,table_id,snapshot_id,catalog_table_id,name)"
            " VALUES('fresh-item',%s,%s,%s,%s,%s)",
            (ordinal, table, snapshot, catalog, f"Member {ordinal}"),
        )
        pin(connection, catalog, "member")
        tables.append(
            dict(catalog_table_id=catalog, table_id=table, snapshot_id=snapshot, n_columns=1, n_rows_actual=2)
        )
    descriptor, digest = freeze(connection)
    receipt = dict(
        domain="structured",
        native_workspace_id="native-space",
        native_source_id=native_dataset,
        native_asset_id=native_dataset,
        sha256="d" * 64,
        size_bytes=7,
        source_version_id=None,
        extraction_id=None,
        n_chunks=0,
        object_key="private/dataset",
        file_version_id="dataset-index",
        native_file_id=native_file,
        tables=tables,
        source_attempt_id="attempt",
        source_publication_sha256=digest,
    )
    return descriptor, receipt


def publish_dataset(connection, receipt):
    connection.execute("SELECT koinon_open_source_publication('attempt',%s)", (Jsonb(receipt),))
    bindings = [
        ("fresh-source", receipt["native_source_id"], {}),
        ("fresh-asset", receipt["native_asset_id"], {}),
        ("dataset-index", receipt["native_file_id"], {}),
    ]
    bindings += [
        (
            t["catalog_table_id"],
            t["table_id"],
            {"file_id": receipt["native_file_id"], "snapshot_id": t["snapshot_id"]},
        )
        for t in receipt["tables"]
    ]
    for identifier, native_id, details in bindings:
        connection.execute("UPDATE lattice_catalog SET status='ready' WHERE id=%s", (identifier,))
        connection.execute(
            "INSERT INTO "
            "lattice_domain_bindings(id,tenant_id,catalog_id,workspace_id,domain,entity_kind,native_id,native_workspace_id,details_json,created_by,created_at)"
            " SELECT "
            "id||'-binding',tenant_id,id,workspace_id,'structured',kind,%s,'native-space',%s,'issuer|alice',now()"
            " FROM lattice_catalog WHERE id=%s",
            (native_id, Jsonb(details), identifier),
        )
    vector = [
        r[0]
        for r in connection.execute(
            "SELECT koinon_publication_current(attempt_id,catalog_id) FROM "
            "koinon_content_publication_targets WHERE attempt_id='attempt' ORDER BY catalog_id"
        ).fetchall()
    ]
    ack = dict(
        schema="koinon.source-publication-acknowledgement.v1",
        attempt_id="attempt",
        descriptor_sha256=receipt["source_publication_sha256"],
        native_receipt=receipt,
        transition_vector=vector,
        live_vector=vector,
    )
    ack_digest = connection.execute(
        "UPDATE koinon_content_publication_baselines SET acknowledgement_json=%s WHERE "
        "attempt_id='attempt' RETURNING acknowledgement_sha256",
        (Jsonb(ack),),
    ).fetchone()[0]
    connection.execute(
        "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt'",
        (Jsonb(receipt),),
    )
    connection.execute(
        "INSERT INTO "
        "koinon_content_imported_assets(asset_id,tenant_id,source_id,initial_attempt_id,created_at)"
        " VALUES('fresh-asset','retained','fresh-source','attempt',now())"
    )
    connection.execute(
        "INSERT INTO "
        "koinon_content_imported_versions(attempt_id,tenant_id,source_id,asset_id,domain,native_workspace_id,native_source_id,native_asset_id,native_version_id,created_at)"
        " "
        "VALUES('attempt','retained','fresh-source','fresh-asset','structured','native-space',%s,%s,'dataset-index',now())",
        (receipt["native_source_id"], receipt["native_asset_id"]),
    )
    connection.execute(
        "UPDATE koinon_content_objects SET "
        "state='imported',published_local_revision=%s,published_native_version_id='dataset-index',published_sha256=%s"
        " WHERE id='origin'",
        ("cpv1:" + ack_digest, "d" * 64),
    )
    connection.execute("UPDATE koinon_content_sync_work SET status='imported' WHERE id='work'")
    connection.execute("UPDATE lattice_jobs SET status='succeeded' WHERE id='job-first'")
    connection.execute(
        "UPDATE koinon_bulk_items SET "
        "status='succeeded',job_id='job-first',native_id=%s,receipt_json=%s WHERE id='fresh-item'",
        (receipt["native_asset_id"], Jsonb(receipt)),
    )
    return ack_digest, vector


@pytest.mark.parametrize("count", [1, 16])
async def test_dataset_acknowledgement_retains_distinct_canonical_and_native_file_ids(source_sessions, count):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        descriptor, receipt = reserve_dataset(connection, count)
        connection.commit()
        ack_digest, vector = publish_dataset(connection, receipt)
        connection.commit()
        assert len(vector) == count + 3
        assert receipt["native_file_id"] != "dataset-index"
        assert connection.execute(
            "SELECT native_id FROM lattice_domain_bindings WHERE catalog_id='dataset-index'"
        ).fetchone() == (receipt["native_file_id"],)
        assert connection.execute(
            "SELECT native_version_id FROM koinon_content_imported_versions WHERE attempt_id='attempt'"
        ).fetchone() == ("dataset-index",)


def publish_document(connection, digest, *, complete=True):
    receipt = native_receipt(digest)
    connection.execute("SELECT koinon_open_source_publication('attempt',%s)", (Jsonb(receipt),))
    for catalog_id, native_id in (("fresh-source", "native-source"), ("fresh-asset", "native-asset")):
        connection.execute("UPDATE lattice_catalog SET status='ready' WHERE id=%s", (catalog_id,))
        connection.execute(
            "INSERT INTO "
            "lattice_domain_bindings(id,tenant_id,catalog_id,workspace_id,domain,entity_kind,native_id,native_workspace_id,details_json,created_by,created_at)"
            " "
            "SELECT "
            "id||'-binding',tenant_id,id,workspace_id,'canon',kind,%s,'native-space',%s,'issuer|alice',now()"
            " FROM lattice_catalog WHERE id=%s",
            (native_id, Jsonb({"source_version_id": "version", "extraction_id": "extraction"}), catalog_id),
        )
    vector = [
        r[0]
        for r in connection.execute(
            "SELECT koinon_publication_current(attempt_id,catalog_id) FROM "
            "koinon_content_publication_targets WHERE attempt_id='attempt' ORDER BY catalog_id"
        ).fetchall()
    ]
    acknowledgement = dict(
        schema="koinon.source-publication-acknowledgement.v1",
        attempt_id="attempt",
        descriptor_sha256=digest,
        native_receipt=receipt,
        transition_vector=vector,
        live_vector=vector,
    )
    ack_digest = connection.execute(
        "UPDATE koinon_content_publication_baselines SET acknowledgement_json=%s WHERE "
        "attempt_id='attempt' RETURNING acknowledgement_sha256",
        (Jsonb(acknowledgement),),
    ).fetchone()[0]
    if complete:
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt'",
            (Jsonb(receipt),),
        )
        connection.execute(
            "INSERT INTO "
            "koinon_content_imported_assets(asset_id,tenant_id,source_id,initial_attempt_id,created_at)"
            " VALUES('fresh-asset','retained','fresh-source','attempt',now())"
        )
        connection.execute(
            "INSERT INTO "
            "koinon_content_imported_versions(attempt_id,tenant_id,source_id,asset_id,domain,native_workspace_id,native_source_id,native_asset_id,native_version_id,extraction_id,created_at)"
            " "
            "VALUES('attempt','retained','fresh-source','fresh-asset','canon','native-space','native-source','native-asset','version','extraction',now())"
        )
        connection.execute(
            "UPDATE koinon_content_objects SET "
            "state='imported',published_local_revision=%s,published_native_version_id='version',published_sha256=%s"
            " WHERE id='origin'",
            ("cpv1:" + ack_digest, "d" * 64),
        )
        connection.execute("UPDATE koinon_content_sync_work SET status='imported' WHERE id='work'")
        connection.execute("UPDATE lattice_jobs SET status='succeeded' WHERE id='job-first'")
        connection.execute(
            "UPDATE koinon_bulk_items SET "
            "status='succeeded',job_id='job-first',native_id='native-asset',receipt_json=%s WHERE"
            " id='fresh-item'",
            (Jsonb(receipt),),
        )
    return ack_digest


async def test_acknowledgement_persists_exact_vector_and_cannot_reopen(source_sessions, source_database):
    _, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        _, digest = freeze(connection)
        connection.commit()
        for table in (
            "koinon_content_publication_baselines",
            "koinon_content_publication_targets",
            "koinon_content_publication_transactions",
            "koinon_content_imported_assets",
            "koinon_content_imported_versions",
            "koinon_content_sync_work",
            "lattice_domain_bindings",
            "lattice_jobs",
        ):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
        connection.commit()
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        ack_digest = publish_document(connection, digest)
        connection.commit()
        assert connection.execute(
            "SELECT published_local_revision FROM koinon_content_objects WHERE id='origin'"
        ).fetchone() == ("cpv1:" + ack_digest,)
        with pytest.raises(psycopg.errors.CheckViolation, match="unacknowledged"), connection.transaction():
            connection.execute(
                "SELECT koinon_open_source_publication('attempt',%s)", (Jsonb(native_receipt(digest)),)
            )
        with pytest.raises(psycopg.errors.CheckViolation, match="immutable"), connection.transaction():
            connection.execute(
                "UPDATE koinon_content_publication_baselines SET acknowledgement_json=NULL WHERE "
                "attempt_id='attempt'"
            )
        assert connection.execute(
            "SELECT closed FROM koinon_content_publication_transactions WHERE attempt_id='attempt'"
        ).fetchone() == (True,)


async def test_acknowledgement_without_source_completion_rolls_back(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        _, digest = freeze(connection)
        connection.commit()
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="completion is incomplete"),
            connection.transaction(),
        ):
            publish_document(connection, digest, complete=False)
        assert connection.execute(
            "SELECT acknowledgement_json FROM koinon_content_publication_baselines WHERE attempt_id='attempt'"
        ).fetchone() == (None,)
        assert connection.execute("SELECT status FROM lattice_catalog WHERE id=%s", (asset,)).fetchone() == (
            "pending",
        )


@pytest.mark.parametrize("write", ["version", "pointer"])
async def test_direct_publication_requires_same_transaction_acknowledgement(
    source_sessions, source_database, write
):
    _, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        load("deploy/provision_roles.py").grant_table(connection, "koinon_content_imported_versions", role)
        reserve_document(connection)
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt'",
            (Jsonb(native_receipt("a" * 64)),),
        )
        connection.execute(
            "INSERT INTO koinon_content_imported_assets"
            "(asset_id,tenant_id,source_id,initial_attempt_id,created_at) "
            "VALUES('fresh-asset','retained','fresh-source','attempt',now())"
        )
        connection.commit()
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="publication.*acknowledgement"),
            connection.transaction(),
        ):
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            if write == "version":
                connection.execute(
                    "INSERT INTO koinon_content_imported_versions"
                    "(attempt_id,tenant_id,source_id,asset_id,domain,native_workspace_id,"
                    "native_source_id,native_asset_id,native_version_id,extraction_id,created_at) "
                    "VALUES('attempt','retained','fresh-source','fresh-asset','canon',"
                    "'native-space','native-source','native-asset','version','extraction',now())"
                )
            else:
                connection.execute(
                    "UPDATE koinon_content_objects SET state='imported',published_local_revision=%s,"
                    "published_native_version_id='version',published_sha256=%s WHERE id='origin'",
                    ("cpv1:" + "b" * 64, "d" * 64),
                )


async def test_receipt_only_forensic_settlement_does_not_publish(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        _, digest = freeze(connection)
        connection.commit()
        connection.execute("UPDATE lattice_catalog SET name=name WHERE id=%s", (asset,))
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt'",
            (Jsonb(native_receipt(digest)),),
        )
        connection.commit()
        assert connection.execute(
            "SELECT receipt_json->>'source_publication_sha256' FROM koinon_content_imports WHERE id='attempt'"
        ).fetchone() == (digest,)
        assert connection.execute("SELECT count(*) FROM koinon_content_imported_versions").fetchone() == (0,)
        assert connection.execute(
            "SELECT published_local_revision,published_native_version_id,published_sha256 "
            "FROM koinon_content_objects WHERE id='origin'"
        ).fetchone() == (None, None, None)


async def test_historical_acknowledgement_cannot_republish_cleared_pointers(source_sessions, source_database):
    _, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        _, digest = freeze(connection)
        connection.commit()
        ack_digest = publish_document(connection, digest)
        connection.commit()
        connection.execute(
            "UPDATE koinon_content_objects SET published_local_revision=NULL,"
            "published_native_version_id=NULL,published_sha256=NULL WHERE id='origin'"
        )
        connection.commit()
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="same-transaction acknowledgement"),
            connection.transaction(),
        ):
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            connection.execute(
                "UPDATE koinon_content_objects SET published_local_revision=%s,"
                "published_native_version_id='version',published_sha256=%s WHERE id='origin'",
                ("cpv1:" + ack_digest, "d" * 64),
            )


def reserve_document_replacement(connection, dataset_receipt=None, *, structure_publication_id=None):
    operation = "dataset.replace" if dataset_receipt else "document.replace"
    metadata = {
        "operation": operation,
        "sha256": "e" * 64,
        "bytes": 8,
        "_koinon_processing": {"state": "unknown", "operation": operation},
    }
    connection.execute(
        "UPDATE koinon_content_objects SET generation=2,remote_version='v2',state='pending' WHERE id='origin'"
    )
    connection.execute(
        "INSERT INTO lattice_catalog SELECT "
        "(jsonb_populate_record(NULL::lattice_catalog,to_jsonb(c)||%s::jsonb)).* FROM "
        "lattice_catalog c WHERE id='fresh-asset'",
        (
            Jsonb(
                {
                    "id": "replacement",
                    "kind": "index_version",
                    "parent_id": "fresh-asset" if dataset_receipt else "fresh-source",
                    "status": "pending",
                    "mutation_revision": 1,
                    "metadata_json": metadata,
                }
            ),
        ),
    )
    connection.execute(
        "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
        "VALUES('replacement-audit','retained','issuer|alice','knowledge.content.recorded','replacement',%s,now())",
        (Jsonb({"operation": operation, "state": "unknown"}),),
    )
    connection.execute(
        "INSERT INTO koinon_content_imports SELECT "
        "(jsonb_populate_record(NULL::koinon_content_imports,to_jsonb(a)||%s::jsonb)).* FROM "
        "koinon_content_imports a WHERE id='attempt'",
        (
            Jsonb(
                {
                    "id": "attempt2",
                    "generation": 2,
                    "intake_item_id": None,
                    "content_operation_id": "replacement",
                    "remote_version": "v2",
                    "sha256": "e" * 64,
                    "size_bytes": 8,
                    "receipt_json": None,
                    "committed_at": None,
                }
            ),
        ),
    )
    connection.execute(
        "INSERT INTO koinon_content_sync_work SELECT "
        "(jsonb_populate_record(NULL::koinon_content_sync_work,to_jsonb(w)||%s::jsonb)).* FROM "
        "koinon_content_sync_work w WHERE id='work'",
        (
            Jsonb(
                {
                    "id": "work2",
                    "generation": 2,
                    "remote_version": "v2",
                    "attempt_id": "attempt2",
                    "status": "admitted",
                }
            ),
        ),
    )
    connection.execute(
        "INSERT INTO koinon_content_sync_observations SELECT "
        "(jsonb_populate_record(NULL::koinon_content_sync_observations,to_jsonb(o)||%s::jsonb)).*"
        " FROM koinon_content_sync_observations o WHERE id='observation'",
        (
            Jsonb(
                {
                    "id": "observation2",
                    "page_sequence": 2,
                    "generation": 2,
                    "remote_version": "v2",
                    "work_id": "work2",
                }
            ),
        ),
    )
    connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=2 WHERE id='first'")
    connection.execute(
        "INSERT INTO "
        "koinon_content_publication_baselines(attempt_id,tenant_id,workspace_id,project_id,mapping_id,object_id,source_id,asset_id,producer_kind,previous_attempt_id,previous_structure_publication_id,created_at)"
        " "
        "VALUES('attempt2','retained','workspace','project','mapping','origin','fresh-source','fresh-asset',%s,'attempt',%s,now())",
        ("replace_dataset" if dataset_receipt else "replace_document", structure_publication_id),
    )
    producer = dict(
        schema="koinon.source-replacement-producer.v1",
        attempt_id="attempt2",
        previous_attempt_id="attempt",
        baseline_sha256=None,
        native_workspace_id="native-space",
        native_dataset_id=None,
        native_file_id=None,
        previous_index_id=None,
        members=[],
    )
    if dataset_receipt:
        producer.update(
            baseline_sha256="b" * 64,
            native_dataset_id=dataset_receipt["native_asset_id"],
            native_file_id=str(uuid4()),
            previous_index_id="dataset-index",
        )
        for ordinal in range(16):
            member = dict(
                schema="koinon.dataset-replacement-member.v1",
                member_key=f"new-member-{ordinal}",
                action="add",
                table_id=str(uuid4()),
                catalog_table_id=f"new-member-{ordinal:02}",
                snapshot_id=str(uuid4()),
                ordinal=ordinal,
                name=f"New {ordinal}",
                parser_fingerprint="parser-v1",
            )
            connection.execute(
                "INSERT INTO lattice_catalog SELECT "
                "(jsonb_populate_record(NULL::lattice_catalog,to_jsonb(c)||%s::jsonb)).* FROM "
                "lattice_catalog c WHERE id='fresh-asset'",
                (
                    Jsonb(
                        {
                            "id": member["catalog_table_id"],
                            "kind": "table",
                            "parent_id": "fresh-asset",
                            "status": "pending",
                            "mutation_revision": 1,
                            "metadata_json": {"snapshot_id": member["snapshot_id"]},
                        }
                    ),
                ),
            )
            producer["members"].append(member)
        for ordinal, old in enumerate(dataset_receipt["tables"]):
            producer["members"].append(
                dict(
                    schema="koinon.dataset-replacement-member.v1",
                    member_key=f"member-{ordinal}",
                    action="remove",
                    table_id=old["table_id"],
                    catalog_table_id=old["catalog_table_id"],
                    snapshot_id=old["snapshot_id"],
                    ordinal=None,
                    name=None,
                    parser_fingerprint="parser-v1",
                )
            )
    connection.execute(
        "UPDATE lattice_catalog SET metadata_json=%s WHERE id='replacement'",
        (Jsonb({**metadata, "_koinon_source_replacement": producer}),),
    )
    predecessor = (
        "koinon_publication_predecessor(h)->'effective_vector'"
        if structure_publication_id
        else "h.acknowledgement_json->'live_vector'"
    )
    connection.execute(
        "INSERT INTO koinon_content_publication_targets SELECT "
        "(jsonb_populate_record(NULL::koinon_content_publication_targets,v||jsonb_build_object('attempt_id','attempt2','disposition',CASE"
        " WHEN v->>'role'='member' THEN 'remove' ELSE 'retain' END,'role',CASE WHEN "
        "v->>'role'='new_index' THEN 'old_index' ELSE v->>'role' END))).* FROM "
        "koinon_content_publication_baselines "
        "h,jsonb_array_elements(" + predecessor + ") v WHERE h.attempt_id=%s",
        ("attempt2" if structure_publication_id else "attempt",),
    )
    if dataset_receipt:
        pin(connection, "replacement", "new_index", attempt="attempt2")
        for member in producer["members"]:
            if member["action"] == "add":
                pin(connection, member["catalog_table_id"], "member", attempt="attempt2")
    return producer


async def test_replacement_freezes_predecessor_and_exact_metadata_write_plan(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        original, digest = freeze(connection)
        connection.commit()
        previous_digest = publish_document(connection, digest)
        connection.commit()
        producer = reserve_document_replacement(connection)
        with pytest.raises(psycopg.errors.CheckViolation, match="immutable"), connection.transaction():
            connection.execute(
                "UPDATE lattice_catalog SET "
                "metadata_json=metadata_json::jsonb-'_koinon_source_replacement' WHERE "
                "id='replacement'"
            )
        descriptor = copy.deepcopy(original)
        descriptor["identity"].update(
            attempt_id="attempt2",
            generation=2,
            producer_kind="replace_document",
            previous_attempt_id="attempt",
        )
        descriptor["producer"] = {"intake_item_id": None, "content_operation_id": "replacement"}
        descriptor["observation"].update(work_id="work2", observation_id="observation2")
        descriptor["content"].update(remote_version="v2", sha256="e" * 64, size_bytes=8)
        descriptor["previous_acknowledgement_sha256"] = previous_digest
        descriptor["native"].update(
            operation_id="replacement",
            expected_heads={
                "baseline_sha256": None,
                "source_version_id": "version",
                "extraction_id": "extraction",
                "native_file_id": None,
                "tables": [],
            },
        )
        for target in descriptor["targets"]:
            identifier = target["pin"]["catalog_id"]
            target["pin"] = connection.execute(
                "SELECT to_jsonb(t)-'attempt_id' FROM koinon_content_publication_targets t WHERE "
                "attempt_id='attempt2' AND catalog_id=%s",
                (identifier,),
            ).fetchone()[0]
            target["writes"][0]["fields"]["metadata"] = {
                "sha256": "e" * 64,
                "bytes": 8,
                "latest_content_version_id": "replacement",
            }
        with pytest.raises(psycopg.errors.CheckViolation, match="write plan"), connection.transaction():
            bad = copy.deepcopy(descriptor)
            bad["targets"][0]["writes"][0]["fields"]["metadata"]["bytes"] = 9
            connection.execute(
                "UPDATE koinon_content_publication_baselines SET descriptor_json=%s WHERE "
                "attempt_id='attempt2'",
                (Jsonb(bad),),
            )
        digest2 = connection.execute(
            "UPDATE koinon_content_publication_baselines SET descriptor_json=%s WHERE "
            "attempt_id='attempt2' RETURNING descriptor_sha256",
            (Jsonb(descriptor),),
        ).fetchone()[0]
        connection.commit()
        receipt = {
            **native_receipt(digest2),
            "source_attempt_id": "attempt2",
            "sha256": "e" * 64,
            "size_bytes": 8,
            "source_version_id": "version2",
            "extraction_id": "extraction2",
        }
        connection.execute("SELECT koinon_open_source_publication('attempt2',%s)", (Jsonb(receipt),))
        for target in descriptor["targets"]:
            identifier = target["pin"]["catalog_id"]
            connection.execute(
                "UPDATE lattice_catalog SET status='ready',metadata_json=%s WHERE id=%s",
                (Jsonb(target["writes"][0]["fields"]["metadata"]), identifier),
            )
            connection.execute(
                "UPDATE lattice_domain_bindings SET details_json=%s WHERE catalog_id=%s",
                (Jsonb({"source_version_id": "version2", "extraction_id": "extraction2"}), identifier),
            )
        vector = [
            r[0]
            for r in connection.execute(
                "SELECT koinon_publication_current(attempt_id,catalog_id) FROM "
                "koinon_content_publication_targets WHERE attempt_id='attempt2' ORDER BY "
                "catalog_id"
            ).fetchall()
        ]
        ack = dict(
            schema="koinon.source-publication-acknowledgement.v1",
            attempt_id="attempt2",
            descriptor_sha256=digest2,
            native_receipt=receipt,
            transition_vector=vector,
            live_vector=vector,
        )
        ack_digest = connection.execute(
            "UPDATE koinon_content_publication_baselines SET acknowledgement_json=%s WHERE "
            "attempt_id='attempt2' RETURNING acknowledgement_sha256",
            (Jsonb(ack),),
        ).fetchone()[0]
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt2'",
            (Jsonb({**receipt, "operation_id": "replacement"}),),
        )
        connection.execute(
            "INSERT INTO koinon_content_imported_versions SELECT "
            "(jsonb_populate_record(NULL::koinon_content_imported_versions,to_jsonb(v)||%s::jsonb)).*"
            " FROM koinon_content_imported_versions v WHERE attempt_id='attempt'",
            (
                Jsonb(
                    {
                        "attempt_id": "attempt2",
                        "native_version_id": "version2",
                        "extraction_id": "extraction2",
                    }
                ),
            ),
        )
        connection.execute(
            "UPDATE koinon_content_objects SET "
            "state='imported',published_local_revision=%s,published_native_version_id='version2',published_sha256=%s"
            " WHERE id='origin'",
            ("cpv1:" + ack_digest, "e" * 64),
        )
        connection.execute("UPDATE koinon_content_sync_work SET status='imported' WHERE id='work2'")
        connection.commit()
        assert connection.execute(
            "SELECT mutation_revision FROM lattice_catalog WHERE id='fresh-asset'"
        ).fetchone() == (3,)
        assert connection.execute(
            "SELECT metadata_json->'_koinon_source_replacement' FROM lattice_catalog WHERE id='replacement'"
        ).fetchone() == (producer,)


async def test_dataset_replacement_bounds_transition_and_excludes_retired_history(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        original, old_receipt = reserve_dataset(connection, 16)
        connection.commit()
        previous_digest, _ = publish_dataset(connection, old_receipt)
        connection.commit()
        producer = reserve_document_replacement(connection, old_receipt)
        descriptor = copy.deepcopy(original)
        descriptor["identity"].update(
            attempt_id="attempt2",
            generation=2,
            producer_kind="replace_dataset",
            previous_attempt_id="attempt",
        )
        descriptor["producer"] = {"intake_item_id": None, "content_operation_id": "replacement"}
        descriptor["observation"].update(work_id="work2", observation_id="observation2")
        descriptor["content"].update(remote_version="v2", sha256="e" * 64, size_bytes=8)
        descriptor["previous_acknowledgement_sha256"] = previous_digest
        descriptor["native"].update(
            operation_id="replacement",
            expected_heads=dict(
                baseline_sha256="b" * 64,
                source_version_id=None,
                extraction_id=None,
                native_file_id=old_receipt["native_file_id"],
                tables=[
                    {k: t[k] for k in ("catalog_table_id", "table_id", "snapshot_id")}
                    for t in old_receipt["tables"]
                ],
            ),
        )
        descriptor["members"] = producer["members"]
        descriptor["targets"] = []
        pins = connection.execute(
            "SELECT to_jsonb(t)-'attempt_id' FROM koinon_content_publication_targets t WHERE "
            "attempt_id='attempt2' ORDER BY catalog_id"
        ).fetchall()
        for (p,) in pins:
            role, identifier = p["role"], p["catalog_id"]
            metadata = connection.execute(
                "SELECT metadata_json FROM lattice_catalog WHERE id=%s", (identifier,)
            ).fetchone()[0]
            binding = dict(
                domain="structured",
                native_workspace_id={"receipt_field": "native_workspace_id"},
                native_id={"receipt_field": "native_source_id" if role == "source" else "native_asset_id"},
                native_version_id=None,
                native_snapshot_id=None,
            )
            fields = {"status": "ready"}
            if role in ("source", "asset"):
                fields["metadata"] = {
                    **metadata,
                    "sha256": "e" * 64,
                    "bytes": 8,
                    "latest_content_version_id": "replacement",
                }
            elif role == "new_index":
                binding.update(
                    native_id={"receipt_field": "native_file_id"},
                    native_version_id={"receipt_field": "native_file_id"},
                )
            elif p["disposition"] == "remove" or role == "old_index":
                binding = {
                    "domain": p["native_domain"],
                    **{
                        k: p[k]
                        for k in (
                            "native_workspace_id",
                            "native_id",
                            "native_version_id",
                            "native_snapshot_id",
                        )
                    },
                }
                fields = {"status": "archived"}
            else:
                member = next(m for m in producer["members"] if m["catalog_table_id"] == identifier)
                ordinal = member["ordinal"]
                fields["metadata"] = {**metadata, "snapshot_id": member["snapshot_id"]}
                binding.update(
                    native_id={"receipt_field": f"tables.{ordinal}.table_id"},
                    native_version_id={"receipt_field": "native_file_id"},
                    native_snapshot_id={"receipt_field": f"tables.{ordinal}.snapshot_id"},
                )
            descriptor["targets"].append(
                dict(
                    pin=p,
                    writes=[] if role == "old_index" else [dict(action="update", fields=fields)],
                    binding=binding,
                )
            )
        assert len(descriptor["targets"]) == 36
        digest = connection.execute(
            "UPDATE koinon_content_publication_baselines SET descriptor_json=%s WHERE "
            "attempt_id='attempt2' RETURNING descriptor_sha256",
            (Jsonb(descriptor),),
        ).fetchone()[0]
        connection.commit()
        new_tables = [
            {
                "catalog_table_id": m["catalog_table_id"],
                "table_id": m["table_id"],
                "snapshot_id": m["snapshot_id"],
                "n_columns": 1,
                "n_rows_actual": 3,
            }
            for m in producer["members"]
            if m["action"] == "add"
        ]
        receipt = {
            **old_receipt,
            "source_attempt_id": "attempt2",
            "source_publication_sha256": digest,
            "sha256": "e" * 64,
            "size_bytes": 8,
            "file_version_id": "replacement",
            "native_file_id": producer["native_file_id"],
            "tables": new_tables,
        }
        connection.execute("SELECT koinon_open_source_publication('attempt2',%s)", (Jsonb(receipt),))
        for target in descriptor["targets"]:
            p = target["pin"]
            for step in target["writes"]:
                fields = step["fields"]
                if "metadata" in fields:
                    connection.execute(
                        "UPDATE lattice_catalog SET status=%s,metadata_json=%s WHERE id=%s",
                        (fields["status"], Jsonb(fields["metadata"]), p["catalog_id"]),
                    )
                else:
                    connection.execute(
                        "UPDATE lattice_catalog SET status=%s WHERE id=%s",
                        (fields["status"], p["catalog_id"]),
                    )
            if p["disposition"] == "add":
                member = next((m for m in new_tables if m["catalog_table_id"] == p["catalog_id"]), None)
                native_id = member["table_id"] if member else receipt["native_file_id"]
                details = (
                    {"file_id": receipt["native_file_id"], "snapshot_id": member["snapshot_id"]}
                    if member
                    else {}
                )
                connection.execute(
                    "INSERT INTO "
                    "lattice_domain_bindings(id,tenant_id,catalog_id,workspace_id,domain,entity_kind,native_id,native_workspace_id,details_json,created_by,created_at)"
                    " SELECT "
                    "id||'-binding',tenant_id,id,workspace_id,'structured',kind,%s,'native-space',%s,'issuer|alice',now()"
                    " FROM lattice_catalog WHERE id=%s",
                    (native_id, Jsonb(details), p["catalog_id"]),
                )
        vector = [
            r[0]
            for r in connection.execute(
                "SELECT koinon_publication_current(attempt_id,catalog_id) FROM "
                "koinon_content_publication_targets WHERE attempt_id='attempt2' ORDER BY "
                "catalog_id"
            )
        ]
        live = [v for v in vector if v["disposition"] != "remove" and v["role"] != "old_index"]
        ack = dict(
            schema="koinon.source-publication-acknowledgement.v1",
            attempt_id="attempt2",
            descriptor_sha256=digest,
            native_receipt=receipt,
            transition_vector=vector,
            live_vector=live,
        )
        ack_digest = connection.execute(
            "UPDATE koinon_content_publication_baselines SET acknowledgement_json=%s WHERE "
            "attempt_id='attempt2' RETURNING acknowledgement_sha256",
            (Jsonb(ack),),
        ).fetchone()[0]
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt2'",
            (Jsonb({**receipt, "operation_id": "replacement"}),),
        )
        connection.execute(
            "INSERT INTO koinon_content_imported_versions SELECT "
            '(jsonb_populate_record(NULL::koinon_content_imported_versions,to_jsonb(v)||\'{"attempt_id":"attempt2","native_version_id":"replacement"}\'::jsonb)).*'
            " FROM koinon_content_imported_versions v WHERE attempt_id='attempt'"
        )
        connection.execute(
            "UPDATE koinon_content_objects SET "
            "state='imported',published_local_revision=%s,published_native_version_id='replacement',published_sha256=%s"
            " WHERE id='origin'",
            ("cpv1:" + ack_digest, "e" * 64),
        )
        connection.execute("UPDATE koinon_content_sync_work SET status='imported' WHERE id='work2'")
        connection.commit()
        assert len(live) == 19
        assert not {t["catalog_table_id"] for t in old_receipt["tables"]} & {v["catalog_id"] for v in live}
        assert connection.execute(
            "SELECT count(*) FROM lattice_catalog WHERE id LIKE 'dataset-member-%%' AND status='archived'"
        ).fetchone() == (16,)
        assert connection.execute(
            "SELECT mutation_revision FROM lattice_catalog WHERE id='dataset-index'"
        ).fetchone() == (2,)


async def test_runtime_updated_old_row_cannot_be_pinned_as_new(source_sessions, source_database):
    _, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        reserve_document(connection, fresh=False)
        load("deploy/provision_roles.py").grant_table(connection, "koinon_content_publication_targets", role)
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        with pytest.raises(psycopg.errors.CheckViolation, match="actual INSERT"), connection.transaction():
            pin(connection, "source", "source")
        connection.execute("RESET ROLE")
        assert connection.execute("SELECT count(*) FROM koinon_content_publication_targets").fetchone() == (
            0,
        )


async def test_original_pins_freeze_and_reject_canonical_aba(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        descriptor, digest = freeze(connection)
        assert (
            digest
            == connection.execute(
                "SELECT encode(sha256(convert_to(%s::jsonb::text,'UTF8')),'hex')", (Jsonb(descriptor),)
            ).fetchone()[0]
        )
        connection.commit()
        connection.execute("UPDATE lattice_catalog SET name='Changed' WHERE id=%s", (asset,))
        connection.execute("UPDATE lattice_catalog SET name='asset' WHERE id=%s", (asset,))
        connection.commit()
        try:
            with pytest.raises(psycopg.errors.CheckViolation, match="original pin changed"):
                connection.execute(
                    "SELECT koinon_open_source_publication('attempt',%s)", (Jsonb(native_receipt(digest)),)
                )
        finally:
            connection.rollback()
        assert connection.execute(
            "SELECT acknowledgement_json FROM koinon_content_publication_baselines WHERE attempt_id='attempt'"
        ).fetchone() == (None,)


async def test_open_publication_requires_exact_writes_and_atomic_completion(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        _, digest = freeze(connection)
        connection.commit()
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="complete acknowledgement"),
            connection.transaction(),
        ):
            connection.execute(
                "SELECT koinon_open_source_publication('attempt',%s)", (Jsonb(native_receipt(digest)),)
            )
            with (
                pytest.raises(psycopg.errors.CheckViolation, match="frozen action"),
                connection.transaction(),
            ):
                connection.execute("UPDATE lattice_catalog SET name=name WHERE id=%s", (source,))
            connection.execute("UPDATE lattice_catalog SET status='ready' WHERE id=%s", (source,))
            with pytest.raises(psycopg.errors.CheckViolation, match="write count"), connection.transaction():
                connection.execute("UPDATE lattice_catalog SET status='ready' WHERE id=%s", (source,))
        assert connection.execute(
            "SELECT count(*) FROM koinon_content_publication_transactions"
        ).fetchone() == (0,)
        assert connection.execute("SELECT status FROM lattice_catalog WHERE id=%s", (source,)).fetchone() == (
            "pending",
        )


@pytest.mark.parametrize(
    "change", ["missing", "reordered", "extra", "float", "binding", "writes", "oversize"]
)
async def test_freeze_rejects_incomplete_or_noncanonical_descriptor(source_sessions, change):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")

        def tamper(d):
            if change == "missing":
                d["targets"].pop()
            elif change == "reordered":
                d["targets"].reverse()
            elif change == "extra":
                d["unknown"] = True
            elif change == "float":
                d["identity"]["generation"] = 1.0
            elif change == "binding":
                d["targets"][0]["binding"]["native_id"] = {"receipt_field": "native_source_id"}
            elif change == "writes":
                d["targets"][0]["writes"].append(copy.deepcopy(d["targets"][0]["writes"][0]))
            else:
                d["content"]["remote_version"] = "ü" * 140000

        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            freeze(connection, tamper)
        assert connection.execute(
            "SELECT descriptor_json FROM koinon_content_publication_baselines WHERE attempt_id='attempt'"
        ).fetchone() == (None,)


async def test_runtime_grants_and_freeze_preserve_append_only_evidence(source_sessions, source_database):
    _, uri = source_sessions
    _, role, _ = source_database
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        freeze(connection)
        for table in (
            "koinon_content_publication_baselines",
            "koinon_content_publication_targets",
            "koinon_content_publication_transactions",
        ):
            if table.endswith("transactions"):
                connection.execute(
                    sql.SQL("GRANT UPDATE(closed) ON {} TO {}").format(
                        sql.Identifier(table), sql.Identifier(role)
                    )
                )
            load("deploy/provision_roles.py").grant_table(connection, table, role)
        assert connection.execute(
            "SELECT has_column_privilege(%s,'koinon_content_publication_transactions','closed','UPDATE')",
            (role,),
        ).fetchone() == (False,)
        with pytest.raises(psycopg.errors.CheckViolation, match="frozen"), connection.transaction():
            pin(connection, source, "source")
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        for statement in (
            "UPDATE koinon_content_publication_targets SET mutation_revision=2",
            "DELETE FROM koinon_content_publication_targets",
            "TRUNCATE koinon_content_publication_targets",
            "UPDATE koinon_content_publication_baselines SET descriptor_sha256=repeat('a',64)",
            "INSERT INTO koinon_content_publication_transactions "
            "VALUES('attempt',pg_current_xact_id(),'{}','{}',false)",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute(statement)
        connection.execute("RESET ROLE")
        assert connection.execute("SELECT count(*) FROM koinon_content_publication_targets").fetchone() == (
            2,
        )


async def test_target_append_serializes_with_descriptor_freeze(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        descriptor, _ = freeze(connection, persist=False)
    first = await psycopg.AsyncConnection.connect(uri)
    second = await psycopg.AsyncConnection.connect(uri, application_name="publication-late-pin")
    pending = None
    try:
        await first.execute(
            "SELECT attempt_id FROM koinon_content_publication_baselines WHERE "
            "attempt_id='attempt' FOR UPDATE"
        )
        pending = asyncio.create_task(
            second.execute(
                "INSERT INTO koinon_content_publication_targets SELECT * FROM "
                "koinon_content_publication_targets WHERE attempt_id='attempt' AND "
                "catalog_id='fresh-source'"
            )
        )
        await wait_for_blocked_connection(uri, "publication-late-pin")
        await first.execute(
            "UPDATE koinon_content_publication_baselines SET descriptor_json=%s WHERE attempt_id='attempt'",
            (Jsonb(descriptor),),
        )
        await first.commit()
        with pytest.raises(psycopg.errors.CheckViolation, match="frozen"):
            await asyncio.wait_for(pending, 5)
        await second.rollback()
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        await first.close()
        await second.close()


def test_structured_source_binding_is_write_once_and_local_cannot_acquire_it(metadata_database):
    uri, _, engine = metadata_database
    assert "source_attempt_id" in {
        c["name"] for c in sa.inspect(engine).get_columns("flyquery_bulk_operations")
    }
    with psycopg.connect(uri) as connection:
        workspace, dataset, _ = native_schema.replacement_dataset(connection)
        local = native_schema.bulk_operation(connection, workspace, dataset)
        with pytest.raises(psycopg.Error, match="Immutable structured"), connection.transaction():
            connection.execute(
                "UPDATE flyquery_bulk_operations SET source_attempt_id='forged' WHERE id=%s", (local,)
            )
        connection.execute("UPDATE flyquery_bulk_operations SET plan_json='[]' WHERE id=%s", (local,))
        assert connection.execute(
            "SELECT source_attempt_id,source_publication_sha256 FROM flyquery_bulk_operations WHERE id=%s",
            (local,),
        ).fetchone() == (None, None)


def test_structured_prepared_and_receipt_require_original_source_binding(metadata_database):
    uri, _, _ = metadata_database
    with psycopg.connect(uri) as connection:
        workspace, dataset, _ = native_schema.replacement_dataset(connection)
        operation = uuid4()
        connection.execute(
            "INSERT INTO "
            "flyquery_bulk_operations(id,tenant_id,workspace_id,dataset_id,file_id,actor,catalog_source_id,catalog_dataset_id,catalog_file_version_id,filename,sha256,size_bytes,status,created_at,source_attempt_id)"
            " "
            "VALUES(%s,'tenant',%s,%s,%s,'reader','source','dataset','version','file.csv',%s,7,'admitted',now(),'attempt')",
            (operation, workspace, dataset, uuid4(), "d" * 64),
        )
        connection.execute("UPDATE flyquery_bulk_operations SET plan_json='[]' WHERE id=%s", (operation,))
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="frozen publication digest"),
            connection.transaction(),
        ):
            connection.execute(
                "UPDATE flyquery_bulk_operations SET status='prepared',prepared_json='[]' WHERE id=%s",
                (operation,),
            )
        connection.execute(
            "UPDATE flyquery_bulk_operations SET source_publication_sha256=%s WHERE id=%s",
            ("a" * 64, operation),
        )
        with pytest.raises(psycopg.Error, match="Immutable structured"), connection.transaction():
            connection.execute(
                "UPDATE flyquery_bulk_operations SET source_publication_sha256=%s WHERE id=%s",
                ("b" * 64, operation),
            )
        connection.execute(
            "UPDATE flyquery_bulk_operations SET status='prepared',prepared_json='[]' WHERE id=%s",
            (operation,),
        )
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="receipt publication binding"),
            connection.transaction(),
        ):
            connection.execute(
                "UPDATE flyquery_bulk_operations SET status='committed',receipt_json='{}' WHERE id=%s",
                (operation,),
            )
        connection.execute(
            "UPDATE flyquery_bulk_operations SET status='committed',receipt_json=%s WHERE id=%s",
            (Jsonb({"source_attempt_id": "attempt", "source_publication_sha256": "a" * 64}), operation),
        )
        assert connection.execute(
            "SELECT status,source_attempt_id FROM flyquery_bulk_operations WHERE id=%s", (operation,)
        ).fetchone() == ("committed", "attempt")


def test_canon_original_binding_is_closed_and_never_retrofitted(source_database):
    target, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "canon", ROOT / "packages/canon/migrations/versions", connection
        )
        command.upgrade(config, "head")
        connection.commit()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        source, artifact = str(uuid4()), str(uuid4())
        connection.execute(
            "INSERT INTO "
            "canon_source_artifacts(id,tenant_id,workspace_id,source_id,role,sha256,bytes,object_key)"
            " VALUES(%s,'tenant','workspace',%s,'original',%s,7,'private/key')",
            (artifact, source, "d" * 64),
        )
        binding = dict(
            schema="koinon.source-publication-binding.v1", attempt_id="attempt", descriptor_sha256="a" * 64
        )
        for bad in (
            {**binding, "extra": True},
            {**binding, "attempt_id": 7},
            {**binding, "descriptor_sha256": "A" * 64},
            None,
        ):
            if bad is None:
                version = str(uuid4())
                connection.execute(
                    "INSERT INTO "
                    "canon_source_versions(id,tenant_id,workspace_id,source_id,artifact_id,logical_key,operation_id)"
                    " VALUES(%s,'tenant','workspace',%s,%s,%s,%s)",
                    (version, source, artifact, version, version),
                )
                with pytest.raises(psycopg.Error), connection.transaction():
                    connection.execute(
                        "UPDATE canon_source_versions SET source_publication_json=%s WHERE id=%s",
                        (Jsonb(binding), version),
                    )
            else:
                with (
                    pytest.raises(psycopg.errors.CheckViolation, match="publication binding"),
                    connection.transaction(),
                ):
                    version = str(uuid4())
                    connection.execute(
                        "INSERT INTO "
                        "canon_source_versions(id,tenant_id,workspace_id,source_id,artifact_id,logical_key,operation_id,source_publication_json)"
                        " VALUES(%s,'tenant','workspace',%s,%s,%s,%s,%s)",
                        (version, source, artifact, version, version, Jsonb(bad)),
                    )
        version = str(uuid4())
        connection.execute(
            "INSERT INTO "
            "canon_source_versions(id,tenant_id,workspace_id,source_id,artifact_id,logical_key,operation_id,source_publication_json)"
            " VALUES(%s,'tenant','workspace',%s,%s,%s,%s,%s)",
            (version, source, artifact, version, version, Jsonb(binding)),
        )
        assert connection.execute(
            "SELECT source_publication_json FROM canon_source_versions WHERE id=%s", (version,)
        ).fetchone() == (binding,)


def test_publication_evidence_expands_without_inventing_legacy_baselines(source_database):
    _, _, engine = source_database
    upgrade_sources(engine)
    inspector = sa.inspect(engine)
    assert {
        "koinon_content_publication_baselines",
        "koinon_content_publication_targets",
    } <= set(inspector.get_table_names())
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM koinon_content_publication_baselines"
            ).scalar_one()
            == 0
        )
        assert (
            connection.exec_driver_sql(
                "SELECT count(*) FROM koinon_catalog_history_identities WHERE "
                "creation_transaction IS NOT NULL"
            ).scalar_one()
            == 0
        )


def test_prior_head_upgrade_rolls_back_and_retries_without_legacy_creation_proof(
    source_database, monkeypatch
):
    _, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0051_audit_provenance")
        connection.commit()
        connection.exec_driver_sql(
            "INSERT INTO "
            "lattice_catalog(id,tenant_id,kind,name,description,status,metadata_json,created_by,updated_by,created_at,updated_at)"
            " "
            "VALUES('legacy','retained','folder','Legacy','','ready','{}','actor','actor',now(),now())"
        )
        connection.commit()
    from koinon.integrations.content_sources import publication_guards

    original = publication_guards.statements

    def interrupted():
        yield next(original())
        raise RuntimeError("controlled migration interruption")

    with monkeypatch.context() as patch:
        patch.setattr(publication_guards, "statements", interrupted)
        with pytest.raises(RuntimeError, match="controlled migration interruption"):
            upgrade_sources(engine)
    assert "koinon_content_publication_baselines" not in sa.inspect(engine).get_table_names()
    assert "creation_transaction" not in {
        c["name"] for c in sa.inspect(engine).get_columns("koinon_catalog_history_identities")
    }
    upgrade_sources(engine)
    upgrade_sources(engine)
    with engine.connect() as connection:
        assert connection.exec_driver_sql(
            "SELECT coverage,creation_transaction FROM koinon_catalog_history_identities WHERE "
            "resource_id='legacy'"
        ).one() == ("complete", None)
        assert (
            connection.exec_driver_sql("SELECT name FROM lattice_catalog WHERE id='legacy'").scalar_one()
            == "Legacy"
        )


async def test_pin_lookup_uses_indexes_among_ten_thousand_unrelated_rows(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        connection.execute(
            "INSERT INTO "
            "lattice_catalog(id,tenant_id,workspace_id,project_id,parent_id,kind,name,description,status,metadata_json,created_by,updated_by,created_at,updated_at)"
            " SELECT "
            "'unrelated-'||n,'retained','workspace','project','folder','folder','Local','','ready','{}','actor','actor',now(),now()"
            " FROM generate_series(1,10000) n"
        )
        connection.execute(
            "INSERT INTO "
            "lattice_domain_bindings(id,tenant_id,catalog_id,workspace_id,domain,entity_kind,native_id,native_workspace_id,details_json,created_by,created_at)"
            " SELECT "
            "'binding-'||n,'retained','unrelated-'||n,'workspace','canon','folder','native-'||n,'native-space','{}','actor',now()"
            " FROM generate_series(1,10000) n"
        )
        connection.execute("ANALYZE lattice_catalog")
        connection.execute("ANALYZE lattice_domain_bindings")
        plan = connection.execute(
            "EXPLAIN(ANALYZE,FORMAT JSON) SELECT c.id,b.native_id FROM "
            "koinon_content_publication_targets t JOIN lattice_catalog c ON c.id=t.catalog_id "
            "LEFT JOIN lattice_domain_bindings b ON b.tenant_id=c.tenant_id AND b.catalog_id=c.id"
            " AND b.domain='canon' WHERE t.attempt_id='attempt' ORDER BY c.id"
        ).fetchone()[0][0]["Plan"]

        def nodes(node):
            yield node
            for child in node.get("Plans", []):
                yield from nodes(child)

        assert plan["Actual Rows"] == 2
        large = [
            n for n in nodes(plan) if n.get("Relation Name") in {"lattice_catalog", "lattice_domain_bindings"}
        ]
        assert len(large) == 2
        assert all(n["Node Type"] in {"Index Scan", "Index Only Scan", "Bitmap Heap Scan"} for n in large)


async def test_creation_transaction_roundtrips_through_runtime_sqlalchemy(source_sessions, source_database):
    from koinon.catalog.history_entities import CatalogHistoryIdentity, RetainedTransactionId

    sessions, uri = source_sessions
    _, role, engine = source_database
    with psycopg.connect(uri) as connection:
        load("deploy/provision_roles.py").grant_table(connection, "koinon_catalog_history_identities", role)
        expected = connection.execute(
            "SELECT creation_transaction FROM koinon_catalog_history_identities WHERE resource_id='source'"
        ).fetchone()[0]
    async with sessions() as session:
        row = await session.get(CatalogHistoryIdentity, ("retained", "source"))
        assert row.creation_transaction == int(expected)
        assert isinstance(row.creation_transaction, int)
        large = sa.text("SELECT '9007199254740993'::xid8 AS value").columns(value=RetainedTransactionId())
        absent = sa.text("SELECT NULL::xid8 AS value").columns(value=RetainedTransactionId())
        assert await session.scalar(large) == 9007199254740993
        assert await session.scalar(absent) is None
    with sa.orm.Session(engine) as session:
        row = session.get(CatalogHistoryIdentity, ("retained", "source"))
        assert row.creation_transaction == int(expected)
        assert session.scalar(large) == 9007199254740993
        assert session.scalar(absent) is None


async def test_frozen_dataset_rejects_newly_reserved_late_member(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        reserve_dataset(connection, 1)
        connection.execute(
            "INSERT INTO lattice_catalog SELECT (jsonb_populate_record(NULL::lattice_catalog,"
            'to_jsonb(c)||\'{"id":"late-member","mutation_revision":1}\'::jsonb)).* '
            "FROM lattice_catalog c WHERE id='dataset-member-00'"
        )
        connection.execute(
            "INSERT INTO koinon_bulk_table_reservations"
            "(item_id,ordinal,table_id,snapshot_id,catalog_table_id,name) "
            "VALUES('fresh-item',1,%s,%s,'late-member','Late')",
            (str(uuid4()), str(uuid4())),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="frozen"), connection.transaction():
            pin(connection, "late-member", "member")
        assert connection.execute(
            "SELECT count(*) FROM koinon_content_publication_targets WHERE catalog_id='late-member'"
        ).fetchone() == (0,)


def test_catalog_insert_evidence_survives_later_noop_update(source_database):
    target, role, engine = source_database
    upgrade_sources(engine)
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO lattice_catalog(id,tenant_id,kind,name,description,status,metadata_json,"
            "created_by,updated_by,created_at,updated_at) "
            "VALUES('fresh','retained','folder','Fresh','','pending','{}','actor','actor',now(),now())"
        )
        created = connection.execute(
            "SELECT creation_transaction::text=pg_current_xact_id()::text "
            "FROM koinon_catalog_history_identities WHERE resource_id='fresh'"
        ).fetchone()
        assert created == (True,)
        connection.commit()
        connection.execute("UPDATE lattice_catalog SET name=name WHERE id='fresh'")
        assert connection.execute(
            "SELECT creation_transaction::text=pg_current_xact_id()::text "
            "FROM koinon_catalog_history_identities WHERE resource_id='fresh'"
        ).fetchone() == (False,)
