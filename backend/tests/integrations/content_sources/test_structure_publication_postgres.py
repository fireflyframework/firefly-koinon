# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Structure proofs preserve content evidence under real PostgreSQL transactions."""

import os
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy.engine import make_url
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import ROOT, load
from test_source_publication_baselines_postgres import (
    freeze,
    native_receipt,
    pin,
    publish_dataset,
    publish_document,
    reserve_dataset,
    reserve_document,
    reserve_document_replacement,
)
from test_sync_schema_postgres import job_and_run

pytestmark = pytest.mark.integration


@pytest.fixture
def source_database(record_property):
    uri = os.environ.get("KOINON_STRUCTURE_PUBLICATION_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires explicitly owned structural publication PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port == 55439
    suffix = uuid4().hex
    database, role = "structure_" + suffix, "structure_runtime_" + suffix
    roles = (role, "structure_worker_" + suffix, "structure_maintenance_" + suffix)
    with psycopg.connect(uri, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database)))
        for identity in roles:
            admin.execute(sql.SQL("CREATE ROLE {} LOGIN NOINHERIT").format(sql.Identifier(identity)))
    target = base.set(database=database)
    record_property("owned_database", database)
    record_property("owned_runtime_role", role)
    engine = sa.create_engine(target.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as connection:
            config = load("deploy/migrate.py").history_config(
                "native", ROOT / "deploy/migrations/native_versions", connection
            )
            command.upgrade(config, "koinon_0044_knowledge_modes")
            connection.commit()
            connection.exec_driver_sql(
                "INSERT INTO lattice_tenants(id,name,created_at) VALUES('retained','Retained',now())"
            )
            connection.commit()
        yield target, role, engine
    finally:
        engine.dispose()
        with psycopg.connect(uri, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
            for identity in roles:
                admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(identity)))


def prepare(connection, *, dataset_count=None, remote_parent="root"):
    if dataset_count is None:
        source, asset, _ = reserve_document(connection)
        pin(connection, source, "source")
        pin(connection, asset, "asset")
        _, digest = freeze(connection)
        connection.commit()
        acknowledgement = publish_document(connection, digest)
    else:
        _, receipt = reserve_dataset(connection, dataset_count)
        connection.commit()
        acknowledgement, _ = publish_dataset(connection, receipt)
    connection.execute("UPDATE koinon_content_sync_runs SET status='succeeded' WHERE id='first'")
    connection.commit()
    connection.execute(
        "INSERT INTO koinon_content_sync_states(mapping_id,tenant_id,accepted_policy_id,enabled,revision,"
        "next_run_at,scan_generation,last_complete_scan_generation,updated_at) "
        "VALUES('mapping','retained','policy-mapping',true,1,now(),0,0,now())"
    )
    job_and_run(connection, "structure")
    connection.execute(
        "UPDATE lattice_jobs SET status='running',worker_id='structure-worker',attempts=1,"
        "lease_until=clock_timestamp()+interval '5 minutes' WHERE id='job-structure'"
    )
    connection.execute(
        "UPDATE koinon_content_sync_work SET status='admitted',error_code='SOURCE_METADATA_PENDING' "
        "WHERE id='work'"
    )
    event = {
        "item": {
            "item_id": "remote-file",
            "kind": "file",
            "name": "Renamed",
            "version": "v1",
            "parents": [remote_parent],
        },
        "ancestry": ["root"] if remote_parent == "root" else [remote_parent, "root"],
    }
    connection.execute(
        "INSERT INTO koinon_content_sync_observations VALUES('structure-observation','retained','mapping',"
        "'structure',1,0,'origin',1,'v1',%s,%s,'work',now())",
        (Jsonb(event), "a" * 64),
    )
    connection.execute(
        "UPDATE koinon_content_sync_runs SET status='running',page_sequence=1 WHERE id='structure'"
    )
    connection.commit()
    return acknowledgement


def begin(connection, operations=None, *, observation="structure-observation"):
    if operations is None:
        operations = '[{"catalog_id":"fresh-source","action":"rename","fields":{"name":"Renamed"}}]'
    return connection.execute(
        "SELECT koinon_begin_source_structure('structure','work',%s,'structure-worker',1,%s::json)",
        (observation, operations),
    ).fetchone()[0]


def rename(connection, catalog="fresh-source"):
    connection.execute(
        "UPDATE lattice_catalog SET name='Renamed',updated_by='issuer|alice',"
        "updated_at=clock_timestamp() WHERE id=%s",
        (catalog,),
    )


def finalize(connection, proof):
    return connection.execute("SELECT koinon_finalize_source_structure(%s)", (proof["proof_id"],)).fetchone()[
        0
    ]


async def test_structure_rename_retains_ack_and_resolves_original_anchor(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        acknowledgement = prepare(connection)
        original = connection.execute(
            "SELECT descriptor_json,descriptor_sha256,acknowledgement_json,acknowledgement_sha256 "
            "FROM koinon_content_publication_baselines WHERE attempt_id='attempt'"
        ).fetchone()
        proof = begin(connection)
        rename(connection)
        assert finalize(connection, proof) == proof
        connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        connection.commit()
        result = connection.execute(
            "SELECT koinon_resolve_source_publication('retained','mapping','origin',%s)",
            (proof["effective_revision"],),
        ).fetchone()[0]
        assert result["content_attempt_id"] == "attempt"
        assert result["content_acknowledgement_sha256"] == acknowledgement
        assert result["structure_publication_id"] == proof["proof_id"]
        assert (
            connection.execute(
                "SELECT descriptor_json,descriptor_sha256,acknowledgement_json,acknowledgement_sha256 "
                "FROM koinon_content_publication_baselines WHERE attempt_id='attempt'"
            ).fetchone()
            == original
        )
        assert connection.execute(
            "SELECT state,published_local_revision,remote_name FROM koinon_content_objects WHERE id='origin'"
        ).fetchone() == ("imported", proof["effective_revision"], "Renamed")


@pytest.mark.parametrize("dataset_count", [None, 16])
async def test_structure_move_preserves_all_native_bindings(source_sessions, dataset_count):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        acknowledgement = prepare(connection, dataset_count=dataset_count, remote_parent="remote-folder")
        connection.execute(
            "INSERT INTO lattice_catalog SELECT (jsonb_populate_record(NULL::lattice_catalog,"
            "to_jsonb(c)||%s::jsonb)).* FROM lattice_catalog c WHERE id='folder'",
            (Jsonb({"id": "destination", "kind": "collection", "parent_id": "folder", "status": "ready"}),),
        )
        connection.execute(
            "INSERT INTO koinon_content_folder_bindings VALUES('retained','mapping','remote-folder',"
            "'destination','root','folder','[\"root\"]',1,now())"
        )
        connection.commit()
        before = connection.execute(
            "SELECT catalog_id,to_jsonb(b) FROM lattice_domain_bindings b ORDER BY catalog_id"
        ).fetchall()
        program = '[{"catalog_id":"fresh-source","action":"move","fields":{"parent_id":"destination"}}]'
        proof = begin(connection, program)
        connection.execute(
            "UPDATE lattice_catalog SET parent_id='destination',updated_by='issuer|alice',"
            "updated_at=clock_timestamp() WHERE id='fresh-source'"
        )
        finalize(connection, proof)
        connection.commit()
        assert connection.execute(
            "SELECT parent_id FROM lattice_catalog WHERE id='fresh-source'"
        ).fetchone() == ("destination",)
        assert (
            connection.execute(
                "SELECT catalog_id,to_jsonb(b) FROM lattice_domain_bindings b ORDER BY catalog_id"
            ).fetchall()
            == before
        )
        resolved = connection.execute(
            "SELECT koinon_resolve_source_publication('retained','mapping','origin',%s)",
            (proof["effective_revision"],),
        ).fetchone()[0]
        assert resolved["content_acknowledgement_sha256"] == acknowledgement
        assert len(resolved["effective_vector"]) == (2 if dataset_count is None else 19)
        assert len(resolved["original_members"]) == (0 if dataset_count is None else 16)


async def test_content_replacement_freezes_structural_predecessor(source_sessions):
    import copy

    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        previous_digest = prepare(connection)
        original = connection.execute(
            "SELECT descriptor_json,descriptor_sha256,acknowledgement_json,acknowledgement_sha256 "
            "FROM koinon_content_publication_baselines WHERE attempt_id='attempt'"
        ).fetchone()
        proof = begin(connection)
        rename(connection)
        finalize(connection, proof)
        connection.commit()
        reserve_document_replacement(connection, structure_publication_id=proof["proof_id"])
        descriptor = copy.deepcopy(original[0])
        descriptor["schema"] = "koinon.source-publication-descriptor.v2"
        descriptor["identity"].update(
            attempt_id="attempt2",
            generation=2,
            producer_kind="replace_document",
            previous_attempt_id="attempt",
            previous_structure_publication_id=proof["proof_id"],
        )
        descriptor["producer"] = {"intake_item_id": None, "content_operation_id": "replacement"}
        descriptor["observation"].update(work_id="work2", observation_id="observation2")
        descriptor["content"].update(remote_version="v2", sha256="e" * 64, size_bytes=8)
        descriptor["previous_acknowledgement_sha256"] = previous_digest
        descriptor["previous_effective_revision"] = proof["effective_revision"]
        descriptor["previous_structure_sha256"] = proof["effective_revision"][5:]
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
            target["pin"] = connection.execute(
                "SELECT to_jsonb(t)-'attempt_id' FROM koinon_content_publication_targets t "
                "WHERE attempt_id='attempt2' AND catalog_id=%s",
                (target["pin"]["catalog_id"],),
            ).fetchone()[0]
            target["writes"][0]["fields"]["metadata"] = {
                "sha256": "e" * 64,
                "bytes": 8,
                "latest_content_version_id": "replacement",
            }
        for field in ("previous_effective_revision", "previous_structure_sha256"):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                invalid = copy.deepcopy(descriptor)
                invalid[field] = "forged"
                connection.execute(
                    "UPDATE koinon_content_publication_baselines SET descriptor_json=%s "
                    "WHERE attempt_id='attempt2'",
                    (Jsonb(invalid),),
                )
        digest = connection.execute(
            "UPDATE koinon_content_publication_baselines SET descriptor_json=%s "
            "WHERE attempt_id='attempt2' RETURNING descriptor_sha256",
            (Jsonb(descriptor),),
        ).fetchone()[0]
        connection.commit()
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "UPDATE koinon_content_publication_baselines SET previous_structure_publication_id=NULL "
                "WHERE attempt_id='attempt2'"
            )
        receipt = {
            **native_receipt(digest),
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
            row[0]
            for row in connection.execute(
                "SELECT koinon_publication_current(attempt_id,catalog_id) FROM "
                "koinon_content_publication_targets WHERE attempt_id='attempt2' ORDER BY catalog_id"
            )
        ]
        ack = dict(
            schema="koinon.source-publication-acknowledgement.v1",
            attempt_id="attempt2",
            descriptor_sha256=digest,
            native_receipt=receipt,
            transition_vector=vector,
            live_vector=vector,
        )
        ack_digest = connection.execute(
            "UPDATE koinon_content_publication_baselines SET acknowledgement_json=%s "
            "WHERE attempt_id='attempt2' RETURNING acknowledgement_sha256",
            (Jsonb(ack),),
        ).fetchone()[0]
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt2'",
            (Jsonb({**receipt, "operation_id": "replacement"}),),
        )
        connection.execute(
            "INSERT INTO koinon_content_imported_versions SELECT "
            "(jsonb_populate_record(NULL::koinon_content_imported_versions,to_jsonb(v)||%s::jsonb)).* "
            "FROM koinon_content_imported_versions v WHERE attempt_id='attempt'",
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
            "UPDATE koinon_content_objects SET state='imported',published_local_revision=%s,"
            "published_native_version_id='version2',published_sha256=%s WHERE id='origin'",
            ("cpv1:" + ack_digest, "e" * 64),
        )
        connection.execute("UPDATE koinon_content_sync_work SET status='imported' WHERE id='work2'")
        connection.commit()
        assert (
            connection.execute(
                "SELECT descriptor_json,descriptor_sha256,acknowledgement_json,acknowledgement_sha256 "
                "FROM koinon_content_publication_baselines WHERE attempt_id='attempt'"
            ).fetchone()
            == original
        )
        assert connection.execute(
            "SELECT koinon_resolve_source_publication('retained','mapping','origin',%s)"
            "->>'content_attempt_id'",
            ("cpv1:" + ack_digest,),
        ).fetchone() == ("attempt2",)


async def test_work_guard_preserves_import_identity(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        with connection.transaction(force_rollback=True):
            connection.execute(
                "UPDATE koinon_content_sync_work SET status='failed',"
                "error_code='SOURCE_RETRY' WHERE id='work'"
            )
            assert connection.execute(
                "SELECT status,error_code FROM koinon_content_sync_work WHERE id='work'"
            ).fetchone() == ("failed", "SOURCE_RETRY")
        for change in ("generation=2", "object_id='other'", "remote_version='v2'", "attempt_id=NULL"):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute("UPDATE koinon_content_sync_work SET " + change + " WHERE id='work'")
        assert connection.execute(
            "SELECT generation,object_id,remote_version,attempt_id "
            "FROM koinon_content_sync_work WHERE id='work'"
        ).fetchone() == (1, "origin", "v1", "attempt")


@pytest.mark.parametrize("timing", ["before", "partial", "after"])
async def test_constraints_cannot_escape_finalization(source_sessions, timing):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            if timing == "before":
                connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
                begin(connection)
            else:
                proof = begin(connection)
                rename(connection)
                if timing == "after":
                    finalize(connection, proof)
                    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
                    connection.execute("UPDATE lattice_catalog SET name='Forged' WHERE id='fresh-source'")
                else:
                    connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
        assert connection.execute(
            "SELECT count(*) FROM koinon_content_structure_publications"
        ).fetchone() == (0,)


@pytest.mark.parametrize(
    "program",
    [
        '[{"catalog_id":"fresh-source","action":"rename","fields":{"name":"Forged"}}]',
        '[{"catalog_id":"fresh-source","action":"rename","action":"rename","fields":{"name":"Renamed"}}]',
        '[{"catalog_id":"fresh-source","action":"rename","fields":{"name":"Renamed","name":"Renamed"}}]',
        "[]",
    ],
)
async def test_closed_program_rejects_forgery(source_sessions, program):
    import json

    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        # A valid admission succeeds first; its rollback leaves the same fixture for the attack.
        with connection.transaction(force_rollback=True):
            proof = begin(connection)
            rename(connection)
            finalize(connection, proof)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            proof = begin(connection, program)
            # If admission regresses, finish the complete program so the deferred
            # incomplete-proof guard cannot supply an unrelated rejection.
            for operation in json.loads(program):
                connection.execute(
                    "UPDATE lattice_catalog SET name=%s,updated_by='issuer|alice',"
                    "updated_at=clock_timestamp() WHERE id=%s",
                    (operation["fields"]["name"], operation["catalog_id"]),
                )
            finalize(connection, proof)


async def test_global_program_rejects_reordered_target_write(source_sessions):
    _, uri = source_sessions
    program = (
        '[{"catalog_id":"fresh-source","action":"rename","fields":{"name":"Renamed"}},'
        '{"catalog_id":"fresh-asset","action":"rename","fields":{"name":"Renamed"}}]'
    )
    with psycopg.connect(uri) as connection:
        prepare(connection)
        with connection.transaction(force_rollback=True):
            proof = begin(connection, program)
            rename(connection)
            rename(connection, "fresh-asset")
            finalize(connection, proof)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            proof = begin(connection, program)
            rename(connection, "fresh-asset")
            rename(connection)
            finalize(connection, proof)
        # Controlled mutation in this invocation's disposable database only.
        # Rolling back restores both trigger DDL and the deliberately invalid history.
        with connection.transaction(force_rollback=True):
            connection.execute("ALTER TABLE lattice_catalog DISABLE TRIGGER zz_structure_catalog")
            proof = begin(connection, program)
            rename(connection, "fresh-asset")
            rename(connection)
            assert finalize(connection, proof) == proof
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
            assert connection.execute(
                "SELECT published_local_revision FROM koinon_content_objects WHERE id='origin'"
            ).fetchone() == (proof["effective_revision"],)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            proof = begin(connection, program)
            rename(connection, "fresh-asset")
            rename(connection)
            finalize(connection, proof)


async def test_runtime_roles_cannot_forge_proofs_or_audit(source_sessions, source_database):
    _, uri = source_sessions
    _, role, _ = source_database
    worker = role.replace("_runtime_", "_worker_")
    maintenance = role.replace("_runtime_", "_maintenance_")
    provisioner = load("deploy/provision_roles.py")
    with psycopg.connect(uri) as connection:
        prepare(connection)
        provisioner.grant_source_structure_role(connection, role, worker=False)
        provisioner.grant_source_structure_role(connection, maintenance, worker=False)
        connection.commit()
        for ordinary in (role, maintenance):
            with connection.transaction(force_rollback=True):
                connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(ordinary)))
                with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                    begin(connection)
        provisioner.grant_source_structure_role(connection, worker, worker=True)
        provisioner.grant_table(connection, "lattice_catalog", worker)
        connection.commit()
        with connection.transaction(force_rollback=True):
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(worker)))
            proof = begin(connection)
            rename(connection)
            finalize(connection, proof)
        # Deliberately excessive runtime grants still cannot forge immutable evidence.
        connection.execute(
            sql.SQL("GRANT ALL ON koinon_content_structure_publications TO {}").format(sql.Identifier(worker))
        )
        connection.execute(sql.SQL("GRANT INSERT ON lattice_audit TO {}").format(sql.Identifier(worker)))
        with connection.transaction(force_rollback=True):
            proof = begin(connection)
            rename(connection)
            finalize(connection, proof)
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
            retained = connection.execute(
                "SELECT to_jsonb(p) FROM koinon_content_structure_publications p"
            ).fetchall()
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute("TRUNCATE koinon_content_structure_publications CASCADE")
            assert (
                connection.execute(
                    "SELECT to_jsonb(p) FROM koinon_content_structure_publications p"
                ).fetchall()
                == retained
            )
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(worker)))
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute("TRUNCATE koinon_content_structure_publications CASCADE")
            for statement in (
                "UPDATE koinon_content_structure_publications SET proof_sha256=repeat('e',64)",
                "DELETE FROM koinon_content_structure_publications",
                "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
                "VALUES('forged','retained','issuer|alice','source.structure.published','origin','{}',now())",
            ):
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(statement)
            assert (
                connection.execute(
                    "SELECT to_jsonb(p) FROM koinon_content_structure_publications p"
                ).fetchall()
                == retained
            )


async def test_fresh_metadata_installs_same_structure_guards(source_sessions, source_database):
    from pyfly.data.relational.sqlalchemy import Base

    # Register the real tables required by the fresh metadata guard installer.
    from koinon.authorized_applications import entities as _applications  # noqa: F401
    from koinon.corporate_identity import entities as _identity  # noqa: F401
    from koinon.knowledge.entities import DomainBinding as _DomainBinding  # noqa: F401
    from koinon.mcp_applications import entities as _clients  # noqa: F401
    from koinon.tokens import entities as _tokens  # noqa: F401

    target, _, engine = source_database
    _, uri = source_sessions
    database = "structure_metadata_" + uuid4().hex
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database)))
    fresh = sa.create_engine(target.set(database=database, drivername="postgresql+psycopg"))
    try:
        Base.metadata.create_all(fresh)
        query = sa.text(
            "SELECT proname,pg_get_functiondef(oid) FROM pg_proc "
            "WHERE pronamespace='public'::regnamespace AND "
            "(proname LIKE 'koinon_structure_%' OR proname LIKE 'koinon_%source_structure' "
            "OR proname='koinon_resolve_source_publication' "
            "OR proname='koinon_publication_header_guard') ORDER BY proname"
        )
        with engine.connect() as migrated, fresh.connect() as metadata:
            installed = migrated.execute(query).all()
            assert len(installed) >= 15
            assert metadata.execute(query).all() == installed
    finally:
        fresh.dispose()
        with psycopg.connect(uri, autocommit=True) as connection:
            connection.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE lattice_jobs SET worker_id='replacement' WHERE id='job-structure'",
        "UPDATE koinon_content_sync_runs SET status='cancelled' WHERE id='structure'",
        "UPDATE koinon_content_connections SET status='disconnected',revision=revision+1 "
        "WHERE id='connection'",
        "UPDATE koinon_content_sync_states SET enabled=false,revision=revision+1 WHERE mapping_id='mapping'",
        "UPDATE lattice_domain_bindings SET native_id='forged' WHERE catalog_id='fresh-source'",
        "UPDATE koinon_content_objects SET remote_name='forged' WHERE id='origin'",
        "UPDATE koinon_content_sync_work SET status='admitted' WHERE id='work'",
    ],
)
async def test_finalization_freezes_participants_after_early_constraints(source_sessions, mutation):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        with connection.transaction(force_rollback=True):
            proof = begin(connection)
            rename(connection)
            finalize(connection, proof)
            connection.execute("SET CONSTRAINTS ALL IMMEDIATE")
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(mutation)
            assert finalize(connection, proof) == proof


async def test_expired_lease_prevents_finalization_and_rolls_back(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            proof = begin(connection)
            rename(connection)
            connection.execute(
                "UPDATE lattice_jobs SET lease_until=clock_timestamp()-interval '1 second' "
                "WHERE id='job-structure'"
            )
            finalize(connection, proof)
        assert connection.execute(
            "SELECT count(*) FROM koinon_content_structure_publications"
        ).fetchone() == (0,)
        assert connection.execute("SELECT name FROM lattice_catalog WHERE id='fresh-source'").fetchone() == (
            "source",
        )


async def test_direct_resolution_uses_hash_index_after_many_transitions(source_sessions, record_property):
    import json

    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        event = connection.execute(
            "SELECT event_json FROM koinon_content_sync_observations WHERE id='structure-observation'"
        ).fetchone()[0]
        connection.commit()
        for ordinal in range(2000):
            observation = "structure-observation" if ordinal == 0 else "observation-" + str(ordinal)
            if ordinal:
                connection.execute(
                    "UPDATE koinon_content_sync_work SET status='admitted',"
                    "error_code='SOURCE_METADATA_PENDING' WHERE id='work'"
                )
                connection.execute(
                    "INSERT INTO koinon_content_sync_observations VALUES(%s,'retained','mapping',"
                    "'structure',%s,0,'origin',1,'v1',%s,%s,'work',now())",
                    (observation, ordinal + 1, Jsonb(event), "a" * 64),
                )
                connection.execute(
                    "UPDATE koinon_content_sync_runs SET page_sequence=%s WHERE id='structure'",
                    (ordinal + 1,),
                )
                connection.commit()
            proof = begin(connection, observation=observation)
            rename(connection)
            finalize(connection, proof)
            connection.commit()
        connection.execute("ANALYZE koinon_content_structure_publications")
        plan = connection.execute(
            "EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) SELECT * FROM koinon_content_structure_publications "
            "WHERE proof_sha256=%s AND tenant_id='retained' AND mapping_id='mapping' AND object_id='origin'",
            (proof["effective_revision"][5:],),
        ).fetchone()[0]
        record_property("structure_resolution_plan", json.dumps(plan))
        relation = connection.execute(
            "SELECT reltuples,relpages FROM pg_class "
            "WHERE oid='koinon_content_structure_publications'::regclass"
        ).fetchone()
        print("Structure relation rows/pages:", relation)
        print("Structure resolver plan:", json.dumps(plan))
        assert "uq_structure_digest" in json.dumps(plan)
        assert "Seq Scan" not in json.dumps(plan)
        resolved = connection.execute(
            "SELECT koinon_resolve_source_publication('retained','mapping','origin',%s)",
            (proof["effective_revision"],),
        ).fetchone()[0]
        assert resolved["structure_publication_id"] == proof["proof_id"]
        assert len(resolved["effective_vector"]) == 2


@pytest.mark.parametrize("rollback", [False, True])
async def test_async_repository_obeys_caller_transaction(source_sessions, rollback):
    import json

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.integrations.content_sources.structure_publication_dtos import StructureWrite
    from koinon.integrations.content_sources.structure_publication_repository import (
        SourceStructurePublications,
    )

    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        acknowledgement = prepare(connection)
    engine = create_async_engine(make_url(uri).set(drivername="postgresql+asyncpg"))
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with sessions.begin() as session:
            repository = SourceStructurePublications(session)
            original = await repository.resolve("retained", "mapping", "origin", "cpv1:" + acknowledgement)
            assert original.content_attempt_id == "attempt"
            assert original.structure_publication_id is None
            assert (
                await repository.completed(
                    tenant="retained", work_id="work", observation_id="structure-observation"
                )
                is None
            )
            proof = await repository.begin(
                run_id="structure",
                work_id="work",
                observation_id="structure-observation",
                worker_id="structure-worker",
                job_attempt=1,
                operations=(StructureWrite(catalog_id="fresh-source", action="rename", value="Renamed"),),
            )
            await session.execute(
                sa.text(
                    "UPDATE lattice_catalog SET name='Renamed',updated_by='issuer|alice',"
                    "updated_at=clock_timestamp() WHERE id='fresh-source'"
                )
            )
            assert await repository.finalize(proof.proof_id) == proof
            if rollback:
                await session.rollback()
        async with sessions.begin() as session:
            repository = SourceStructurePublications(session)
            completed = await repository.completed(
                tenant="retained", work_id="work", observation_id="structure-observation"
            )
            assert completed == (None if rollback else proof)
            revision = await session.scalar(
                sa.text("SELECT published_local_revision FROM koinon_content_objects WHERE id='origin'")
            )
            assert revision == ("cpv1:" + acknowledgement if rollback else proof.effective_revision)
            resolved = await repository.resolve("retained", "mapping", "origin", revision)
            assert resolved.content_attempt_id == "attempt"
            assert resolved.content_acknowledgement_sha256 == acknowledgement
            assert json.loads(resolved.native_receipt_json) == json.loads(original.native_receipt_json)
            assert len(json.loads(resolved.effective_vector_json)) == 2
            assert await repository.resolve("other", "mapping", "origin", revision) is None
    finally:
        await engine.dispose()


async def test_finalization_holds_worker_lock_through_commit(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as publication, psycopg.connect(uri) as revocation:
        prepare(publication)
        proof = begin(publication)
        rename(publication)
        finalize(publication, proof)
        publication.execute("SET CONSTRAINTS ALL IMMEDIATE")
        with pytest.raises(psycopg.errors.LockNotAvailable), revocation.transaction():
            revocation.execute("SET LOCAL lock_timeout='100ms'")
            revocation.execute("UPDATE lattice_jobs SET worker_id='replacement' WHERE id='job-structure'")
        publication.commit()
        revocation.execute("UPDATE lattice_jobs SET worker_id='replacement' WHERE id='job-structure'")
        revocation.commit()
        assert publication.execute(
            "SELECT published_local_revision FROM koinon_content_objects WHERE id='origin'"
        ).fetchone() == (proof["effective_revision"],)


async def test_prior_revocation_prevents_new_structure_proof(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as publication, psycopg.connect(uri) as revocation:
        prepare(publication)
        with publication.transaction(force_rollback=True):
            proof = begin(publication)
            rename(publication)
            finalize(publication, proof)
        revocation.execute("UPDATE lattice_jobs SET worker_id='replacement' WHERE id='job-structure'")
        revocation.commit()
        with pytest.raises(psycopg.errors.CheckViolation), publication.transaction():
            begin(publication)
        assert publication.execute(
            "SELECT count(*) FROM koinon_content_structure_publications"
        ).fetchone() == (0,)


async def test_program_operation_and_byte_bounds(source_sessions):
    import json

    _, uri = source_sessions
    operation = {"catalog_id": "fresh-source", "action": "rename", "fields": {"name": "Renamed"}}
    with psycopg.connect(uri) as connection:
        prepare(connection)
        with connection.transaction(force_rollback=True):
            proof = begin(connection, json.dumps([operation] * 100))
            for _ in range(100):
                rename(connection)
            finalize(connection, proof)
        for invalid in (
            json.dumps([operation] * 101),
            json.dumps([{**operation, "fields": {"name": "x" * 262144}}]),
        ):
            # Require admission itself to reject, before any deferred check.
            with connection.transaction(force_rollback=True), pytest.raises(psycopg.errors.CheckViolation):
                begin(connection, invalid)


async def test_structure_rejects_late_descendant_and_preserves_transaction(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        proof = begin(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "INSERT INTO lattice_catalog SELECT (jsonb_populate_record(NULL::lattice_catalog,"
                "to_jsonb(c)||%s::jsonb)).* FROM lattice_catalog c WHERE id='fresh-asset'",
                (Jsonb({"id": "late-descendant", "parent_id": "fresh-source"}),),
            )
        rename(connection)
        finalize(connection, proof)
        connection.commit()
        assert (
            connection.execute("SELECT id FROM lattice_catalog WHERE id='late-descendant'").fetchone() is None
        )
