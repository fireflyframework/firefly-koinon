# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real PostgreSQL contracts for durable sync and aggregate reader preferences."""

import asyncio
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from psycopg.types.json import Json
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_concurrency_postgres import wait_for_blocked_connection
from test_source_migration_postgres import ROOT, load, upgrade_sources
from test_source_migration_postgres import source_database as source_database

pytestmark = pytest.mark.integration
OWNER = "issuer|alice"
TABLES = (
    "koinon_content_policies",
    "koinon_content_sync_states",
    "koinon_content_sync_runs",
    "koinon_content_sync_work",
    "koinon_content_sync_observations",
    "koinon_content_folder_bindings",
    "koinon_content_imported_assets",
    "koinon_content_imported_versions",
    "koinon_content_reader_sets",
    "koinon_content_reader_selections",
    "koinon_content_reader_operations",
)


async def test_sync_schema_matches_entities_and_runtime_cannot_destroy_origins(
    source_sessions, source_database
):
    _, uri = source_sessions
    _, role, engine = source_database
    with psycopg.connect(uri) as connection:
        for table in TABLES:
            assert connection.execute("SELECT to_regclass(%s)", (table,)).fetchone()[0] == table
            load("deploy/provision_roles.py").grant_table(connection, table, role)
            assert connection.execute(
                "SELECT has_table_privilege(%s,%s,'DELETE'),has_table_privilege(%s,%s,'TRUNCATE')",
                (role, table) * 2,
            ).fetchone() == (False, False)
        for table in (
            "koinon_content_imported_assets",
            "koinon_content_imported_versions",
            "koinon_content_reader_selections",
            "koinon_content_reader_operations",
        ):
            assert not connection.execute(
                "SELECT has_table_privilege(%s,%s,'UPDATE')", (role, table)
            ).fetchone()[0]
        assert connection.execute(
            "SELECT item_id,generation FROM koinon_content_objects WHERE id='origin'"
        ).fetchone() == ("remote-file", 1)
    from koinon.integrations.content_sources import reader_entities, sync_entities

    inspector = sa.inspect(engine)
    for module in (reader_entities, sync_entities):
        for entity in vars(module).values():
            if not isinstance(entity, type) or getattr(entity, "__tablename__", None) not in TABLES:
                continue
            actual = {column["name"]: column for column in inspector.get_columns(entity.__tablename__)}
            assert set(actual) == set(entity.__table__.columns.keys())
            assert all(
                actual[column.name]["nullable"] == column.nullable for column in entity.__table__.columns
            )


def selection_header(connection):
    connection.execute(
        (
            "INSERT INTO koinon_content_reader_sets(tenant_id,owner,revision,updated_at) "
            "VALUES('retained',%s,0,now())"
        ),
        (OWNER,),
    )


def replace_selection(connection, expected, operation, *, connection_id="connection", payload="a" * 64):
    revision = expected + 1
    connection.execute(
        (
            "INSERT INTO koinon_content_reader_selections VALUES('retained',%s,%s,"
            "'google_drive','none:',NULL,%s,now())"
        ),
        (OWNER, revision, connection_id),
    )
    connection.execute(
        "INSERT INTO koinon_content_reader_operations VALUES('retained',%s,%s,%s,%s,now())",
        (OWNER, operation, payload, revision),
    )
    return connection.execute(
        (
            "UPDATE koinon_content_reader_sets SET revision=%s,updated_at=now() WHERE "
            "tenant_id='retained' AND owner=%s AND revision=%s RETURNING revision"
        ),
        (revision, OWNER, expected),
    ).fetchone()


async def test_reader_snapshot_is_atomic_and_cannot_be_rebound(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as writer:
        selection_header(writer)
        writer.commit()
        assert replace_selection(writer, 0, "operation-one") == (1,)
        with psycopg.connect(uri) as reader:
            assert reader.execute("SELECT revision FROM koinon_content_reader_sets").fetchone() == (0,)
            assert reader.execute("SELECT count(*) FROM koinon_content_reader_selections").fetchone() == (0,)
        writer.commit()
        for statement in (
            "UPDATE koinon_content_reader_selections SET connection_id='other'",
            "UPDATE koinon_content_reader_operations SET payload_sha256='changed'",
            "UPDATE koinon_content_reader_sets SET revision=0",
            "DELETE FROM koinon_content_reader_selections",
            "TRUNCATE koinon_content_reader_operations",
        ):
            with pytest.raises(psycopg.Error), writer.transaction():
                writer.execute(statement)
        with pytest.raises(psycopg.Error), writer.transaction():
            replace_selection(writer, 1, "bad-owner", connection_id="foreign")
        # An empty snapshot advances the aggregate; retained old rows are no longer selected.
        writer.execute(
            "INSERT INTO koinon_content_reader_operations VALUES('retained',%s,'empty',%s,2,now())",
            (OWNER, "b" * 64),
        )
        writer.execute("UPDATE koinon_content_reader_sets SET revision=2,updated_at=now()")
        assert writer.execute(
            "SELECT count(*) FROM koinon_content_reader_selections s JOIN "
            "koinon_content_reader_sets h USING(tenant_id,owner) WHERE "
            "s.set_revision=h.revision"
        ).fetchone() == (0,)
        assert writer.execute("SELECT count(*) FROM koinon_content_reader_selections").fetchone() == (1,)


async def test_object_generation_cannot_regress_or_change_identity(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        connection.execute("UPDATE koinon_content_objects SET generation=2 WHERE id='origin'")
        for statement in (
            "UPDATE koinon_content_objects SET generation=1 WHERE id='origin'",
            "UPDATE koinon_content_objects SET generation=4 WHERE id='origin'",
            "UPDATE koinon_content_objects SET item_id='substituted' WHERE id='origin'",
        ):
            with pytest.raises(psycopg.Error), connection.transaction():
                connection.execute(statement)


def policy(
    connection,
    mapping="mapping",
    *,
    tenant="retained",
    accepted=True,
    ancestry=None,
    authority_sha256="a" * 64,
):
    connection.execute(
        (
            "INSERT INTO koinon_content_policies(id,tenant_id,owner,mapping_id,revision,"
            "mapping_revision,authority_sha256,policy_json,policy_sha256,root_ancestry_json,"
            "review_id,review_digest,review_expires_at,accepted_by,accepted_session_hash,"
            "accepted_operation_id,accepted_at,created_at) "
            "VALUES(%s,%s,%s,%s,1,1,%s,'{}',%s,%s,%s,%s,now()+interval '1 day',%s,%s,%s,%s,now())"
        ),
        (
            "policy-" + mapping,
            tenant,
            OWNER,
            mapping,
            authority_sha256,
            "b" * 64,
            Json(ancestry or ["root"]),
            "review-" + mapping,
            "c" * 64,
            None,
            None,
            None,
            None,
        ),
    )
    if accepted:
        accept_policy(connection, mapping, tenant=tenant)


def accept_policy(connection, mapping="mapping", *, tenant="retained"):
    operation, receipt = str(uuid4()), str(uuid4())
    identifier, revision, digest, expires = connection.execute(
        "SELECT id,revision,review_digest,review_expires_at FROM koinon_content_policies "
        "WHERE tenant_id=%s AND mapping_id=%s",
        (tenant, mapping),
    ).fetchone()
    connection.execute(
        "UPDATE koinon_content_policies SET accepted_by=%s,accepted_session_hash=%s,"
        "accepted_operation_id=%s,accepted_at=now() WHERE id=%s",
        (OWNER, "d" * 64, operation, identifier),
    )
    # Older-head upgrade tests intentionally exercise the pre-receipt schema.
    if connection.execute("SELECT to_regclass('koinon_content_policy_operations')").fetchone()[0]:
        result = dict(
            schema="koinon.source-policy-operation.v1",
            receipt_id=receipt,
            operation_id=operation,
            action="apply",
            mapping_id=mapping,
            policy_id=identifier,
            expected_policy_revision=revision,
            result_policy_revision=revision,
            review_digest=digest,
            review_expires_at=expires.isoformat(),
            disposition="accepted",
        )
        connection.execute(
            "INSERT INTO koinon_content_policy_operations(id,tenant_id,owner,operation_id,action,"
            "mapping_id,policy_id,expected_policy_revision,result_policy_revision,payload_sha256,"
            "result_json,created_at) VALUES(%s,%s,%s,%s,'apply',%s,%s,%s,%s,%s,%s,now())",
            (
                receipt,
                tenant,
                OWNER,
                operation,
                mapping,
                identifier,
                revision,
                revision,
                "e" * 64,
                Json(result),
            ),
        )


def state(connection, mapping="mapping", *, tenant="retained", enabled=True):
    connection.execute(
        "INSERT INTO koinon_content_sync_states VALUES(%s,%s,%s,%s,1,now(),NULL,0,0,now())",
        (mapping, tenant, "policy-" + mapping, enabled),
    )


def clone_mapping(connection, identifier, *, root="child", tenant="retained", account="connection"):
    connection.execute(
        (
            "INSERT INTO koinon_content_mappings SELECT "
            "(jsonb_populate_record(NULL::koinon_content_mappings,to_jsonb(m)||%s::jsonb)).* "
            "FROM koinon_content_mappings m WHERE id='mapping'"
        ),
        (Json({"id": identifier, "root_id": root, "tenant_id": tenant, "connection_id": account}),),
    )


def job_and_run(connection, identifier, *, mapping="mapping", tenant="retained"):
    connection.execute(
        (
            "INSERT INTO lattice_jobs(id,tenant_id,resource_id,kind,idempotency_key,"
            "payload_hash,payload,status,attempts,max_attempts,progress,available_at,"
            "created_at,updated_at) "
            "VALUES(%s,%s,%s,'content.source.reconcile',%s,%s,'{}','queued',0,3,0,now(),now(),now())"
        ),
        ("job-" + identifier, tenant, mapping, identifier, "a" * 64),
    )
    connection.execute(
        (
            "INSERT INTO koinon_content_sync_runs(id,tenant_id,mapping_id,policy_id,"
            "mapping_revision,connection_revision,job_id,trigger_kind,operation_id,"
            "payload_sha256,status,page_sequence,scan_generation,enumeration_complete,"
            "counters_json,created_at,updated_at) "
            "VALUES(%s,%s,%s,%s,1,1,%s,'manual',%s,%s,'queued',0,1,false,'{}',now(),now())"
        ),
        (identifier, tenant, mapping, "policy-" + mapping, "job-" + identifier, identifier, "b" * 64),
    )


async def opposing_write(uri, application, winner, loser, *, rejected=True):
    """The second connection is observed blocked before the first commits."""
    first = await psycopg.AsyncConnection.connect(uri)
    second = await psycopg.AsyncConnection.connect(uri, application_name=application)
    task = None
    try:
        await first.execute(*winner)
        task = asyncio.create_task(second.execute(*loser))
        await wait_for_blocked_connection(uri, application)
        await first.commit()
        if rejected:
            with pytest.raises(psycopg.errors.CheckViolation):
                await task
        else:
            assert (await task).rowcount == 0
        await second.rollback()
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await second.close()


async def test_accepted_policy_and_cross_account_overlap_are_serialized_per_tenant(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection, accepted=False)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            state(connection)
        accept_policy(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("UPDATE koinon_content_policies SET review_digest='tampered'")
        connection.execute(
            "INSERT INTO koinon_content_connections SELECT "
            "(jsonb_populate_record(NULL::koinon_content_connections,"
            'to_jsonb(c)||\'{"id":"second-account",'
            '"external_subject":"another-account"}\'::jsonb)).* FROM '
            "koinon_content_connections c WHERE id='connection'"
        )
        clone_mapping(connection, "nested", account="second-account")
        policy(connection, "nested", ancestry=["root", "child"])
    await opposing_write(
        uri,
        "overlapping-activation",
        (
            (
                "INSERT INTO koinon_content_sync_states VALUES('mapping','retained',"
                "'policy-mapping',true,1,now(),NULL,0,0,now())"
            ),
        ),
        (
            (
                "INSERT INTO koinon_content_sync_states VALUES('nested','retained',"
                "'policy-nested',true,1,now(),NULL,0,0,now())"
            ),
        ),
    )
    with psycopg.connect(uri) as connection:
        connection.execute("INSERT INTO lattice_tenants VALUES('independent','Independent',now())")
        connection.execute(
            "INSERT INTO koinon_content_connections SELECT "
            "(jsonb_populate_record(NULL::koinon_content_connections,"
            'to_jsonb(c)||\'{"id":"independent-account",'
            '"tenant_id":"independent"}\'::jsonb)).* FROM koinon_content_connections c WHERE '
            "id='connection'"
        )
        clone_mapping(
            connection, "independent-map", root="root", tenant="independent", account="independent-account"
        )
        policy(connection, "independent-map", tenant="independent")
        state(connection, "independent-map", tenant="independent")
        assert connection.execute(
            "SELECT count(*) FROM koinon_content_sync_states WHERE enabled"
        ).fetchone() == (2,)


async def test_active_run_admission_and_generation_cas_have_one_winner(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        job_and_run(connection, "first")
        connection.execute(
            "UPDATE koinon_content_sync_runs SET status='succeeded',finished_at=now() WHERE id='first'"
        )
        job_and_run(connection, "second")
        connection.execute(
            "UPDATE koinon_content_sync_runs SET status='succeeded',finished_at=now() WHERE id='second'"
        )
    # Reopening terminal execution is rejected, independently of the partial unique index.
    with (
        psycopg.connect(uri) as connection,
        pytest.raises(psycopg.errors.CheckViolation),
        connection.transaction(),
    ):
        connection.execute("UPDATE koinon_content_sync_runs SET status='running' WHERE id='first'")
    first = await psycopg.AsyncConnection.connect(uri)
    second = await psycopg.AsyncConnection.connect(uri, application_name="active-run-admission")
    try:
        # Jobs can be admitted separately; the active-run index admits exactly one trigger.
        with psycopg.connect(uri) as connection:
            for identifier in ("third", "fourth"):
                connection.execute(
                    (
                        "INSERT INTO lattice_jobs SELECT (jsonb_populate_record(NULL::lattice_jobs,"
                        "to_jsonb(j)||%s::jsonb)).* FROM lattice_jobs j WHERE id='job-first'"
                    ),
                    (Json({"id": "job-" + identifier, "idempotency_key": identifier}),),
                )
        statement = (
            "INSERT INTO koinon_content_sync_runs SELECT "
            "(jsonb_populate_record(NULL::koinon_content_sync_runs,"
            "to_jsonb(r)||%s::jsonb)).* FROM koinon_content_sync_runs r WHERE id='first'"
        )
        await first.execute(
            statement,
            (
                Json(
                    {
                        "id": "third",
                        "job_id": "job-third",
                        "operation_id": "third",
                        "status": "queued",
                        "finished_at": None,
                    }
                ),
            ),
        )
        pending = asyncio.create_task(
            second.execute(
                statement,
                (
                    Json(
                        {
                            "id": "fourth",
                            "job_id": "job-fourth",
                            "operation_id": "fourth",
                            "status": "queued",
                            "finished_at": None,
                        }
                    ),
                ),
            )
        )
        await wait_for_blocked_connection(uri, "active-run-admission")
        await first.commit()
        with pytest.raises(psycopg.errors.UniqueViolation):
            await pending
        await second.rollback()
    finally:
        await first.close()
        await second.close()
    await opposing_write(
        uri,
        "generation-cas",
        ("UPDATE koinon_content_objects SET generation=2 WHERE id='origin' AND generation=1",),
        ("UPDATE koinon_content_objects SET generation=2 WHERE id='origin' AND generation=1",),
        rejected=False,
    )


async def test_reader_conflicting_put_and_abandoned_snapshot_cannot_advance(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        selection_header(connection)
    statement = "INSERT INTO koinon_content_reader_operations VALUES('retained',%s,%s,%s,1,now())"
    first = await psycopg.AsyncConnection.connect(uri)
    second = await psycopg.AsyncConnection.connect(uri, application_name="reader-selection-cas")
    try:
        await first.execute(statement, (OWNER, "first", "a" * 64))
        await first.execute("UPDATE koinon_content_reader_sets SET revision=1")
        pending = asyncio.create_task(second.execute(statement, (OWNER, "second", "b" * 64)))
        await wait_for_blocked_connection(uri, "reader-selection-cas")
        await first.commit()
        with pytest.raises(psycopg.errors.CheckViolation):
            await pending
        await second.rollback()
    finally:
        await first.close()
        await second.close()
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(uri) as connection:
        connection.execute(
            (
                "INSERT INTO koinon_content_reader_selections VALUES('retained',%s,2,"
                "'google_drive','none:',NULL,'connection',now())"
            ),
            (OWNER,),
        )
        # A crash/bug omitting the header cannot leave a future snapshot committed.


def work_and_observation(connection, identifier="observation", run="first"):
    connection.execute(
        (
            "INSERT INTO koinon_content_sync_work(id,tenant_id,mapping_id,object_id,"
            "generation,remote_version,event_sha256,status,expected_local_revision,"
            "expected_sha256,created_at,updated_at) VALUES('work','retained','mapping',"
            "'origin',1,'v1',%s,'admitted','local-revision',%s,now(),now()) ON CONFLICT DO "
            "NOTHING"
        ),
        ("a" * 64, "b" * 64),
    )
    connection.execute(
        (
            "INSERT INTO koinon_content_sync_observations VALUES(%s,'retained','mapping',%s,"
            "1,0,'origin',1,'v1','{}',%s,'work',now())"
        ),
        (identifier, run, "a" * 64),
    )


async def test_page_work_and_checkpoint_are_atomic_and_work_survives_later_runs(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        job_and_run(connection, "first")
    with pytest.raises(psycopg.errors.CheckViolation), psycopg.connect(uri) as connection:
        work_and_observation(connection)
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT count(*) FROM koinon_content_sync_work").fetchone() == (0,)
        work_and_observation(connection)
        connection.execute(
            "UPDATE koinon_content_sync_runs SET page_sequence=1,cursor_ciphertext=%s WHERE id='first'",
            (b"encrypted-page",),
        )
    with psycopg.connect(uri) as connection:
        connection.execute(
            "UPDATE koinon_content_sync_runs SET status='succeeded',"
            "enumeration_complete=true WHERE id='first'"
        )
        job_and_run(connection, "second")
        work_and_observation(connection, "later-observation", "second")
        connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=1 WHERE id='second'")
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("UPDATE koinon_content_sync_work SET expected_local_revision='edited'")
        assert connection.execute("SELECT count(*) FROM koinon_content_sync_work").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM koinon_content_sync_observations").fetchone() == (2,)


def attempt(connection):
    connection.execute(
        (
            "INSERT INTO koinon_content_imports(id,tenant_id,mapping_id,mapping_revision,"
            "object_id,generation,intake_item_id,provider,external_subject,drive_id,"
            "remote_item_id,remote_version,source_id,asset_id,sha256,size_bytes,created_at) "
            "VALUES('attempt','retained','mapping',1,'origin',1,'item','google_drive',"
            "'provider-alice','drive','remote-file','v1','source','asset',%s,7,now())"
        ),
        ("d" * 64,),
    )


async def test_import_marker_and_exact_receipt_are_immutable_and_roll_back_together(
    source_sessions, source_database
):
    _, uri = source_sessions
    _, role, _ = source_database
    receipt = {
        "domain": "canon",
        "native_workspace_id": "native-space",
        "native_source_id": "native-source",
        "native_asset_id": "native-document",
        "source_version_id": "native-version",
        "extraction_id": "extraction",
        "sha256": "d" * 64,
        "size_bytes": 7,
    }
    version = (
        "INSERT INTO koinon_content_imported_versions VALUES('attempt','retained',"
        "'source','asset','canon','native-space','native-source','native-document',"
        "'native-version','extraction',now())"
    )
    with psycopg.connect(uri) as connection:
        attempt(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "INSERT INTO koinon_content_imported_assets VALUES('asset','retained','source',"
                "'missing-attempt',now())"
            )
        connection.execute(
            "INSERT INTO koinon_content_imported_assets VALUES('asset','retained','source','attempt',now())"
        )
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(version)
        connection.execute(
            "UPDATE koinon_content_imports SET receipt_json=%s,committed_at=now() WHERE id='attempt'",
            (Json(receipt),),
        )
        connection.execute(version)
        for statement in (
            "UPDATE koinon_content_imported_assets SET source_id='folder'",
            "UPDATE koinon_content_imported_versions SET native_version_id='substituted'",
            "UPDATE koinon_content_imports SET receipt_json='{}'",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)
        roles = load("deploy/provision_roles.py")
        for table in TABLES:
            roles.grant_table(connection, table, role)
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        for statement in (
            "DELETE FROM koinon_content_imported_assets",
            "TRUNCATE koinon_content_imported_versions",
            "UPDATE koinon_content_imported_versions SET native_version_id='other'",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute(statement)
    # Failed classification rolls back the pending catalog write in the same transaction.
    with psycopg.connect(uri) as connection:
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "INSERT INTO lattice_catalog SELECT (jsonb_populate_record(NULL::lattice_catalog,"
                'to_jsonb(c)||\'{"id":"pending-asset"}\'::jsonb)).* FROM lattice_catalog c WHERE '
                "id='asset'"
            )
            with psycopg.connect(uri) as reader:
                assert reader.execute(
                    "SELECT count(*) FROM lattice_catalog WHERE id='pending-asset'"
                ).fetchone() == (0,)
            connection.execute(
                "INSERT INTO koinon_content_imported_assets VALUES('pending-asset','retained',"
                "'source','attempt',now())"
            )
        assert connection.execute(
            "SELECT count(*) FROM lattice_catalog WHERE id='pending-asset'"
        ).fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM koinon_content_imported_assets").fetchone() == (1,)


def test_upgrade_from_applied_source_schema_preserves_existing_object(source_database):
    _, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0045_content_sources")
        connection.commit()
        connection.exec_driver_sql(
            "INSERT INTO koinon_content_connections(id,tenant_id,owner,provider,status,"
            "revision,config_fingerprint,scopes,created_at,updated_at) VALUES('old-account',"
            "'retained','old-owner','google_drive','connected',1,'','[]',now(),now())"
        )
        connection.exec_driver_sql(
            "INSERT INTO koinon_content_mappings(id,tenant_id,owner,connection_id,provider,"
            "external_subject,issuer,config_fingerprint,drive_id,root_id,workspace_id,"
            "project_id,parent_id,request_json,request_sha256,status,revision,reviewed_at,"
            "created_at,updated_at) VALUES('old-map','retained','old-owner','old-account',"
            "'google_drive','subject','issuer','','drive','root','space','project','parent',"
            "'{}','digest','active',3,now(),now(),now())"
        )
        connection.exec_driver_sql(
            "INSERT INTO koinon_content_objects VALUES('old-object','retained','old-map',"
            "'old-remote',7,3,'opaque-version','imported',now())"
        )
        before = connection.exec_driver_sql("SELECT to_jsonb(o) FROM koinon_content_objects o").scalar_one()
        connection.commit()
    upgrade_sources(engine)
    with engine.connect() as connection:
        after = connection.exec_driver_sql("SELECT to_jsonb(o) FROM koinon_content_objects o").scalar_one()
        assert {key: after[key] for key in before} == before
        assert all(value is None for key, value in after.items() if key not in before)
        assert connection.exec_driver_sql("SELECT count(*) FROM koinon_content_sync_states").scalar_one() == 0


async def test_folder_binding_preserves_identity_and_validates_tenant_parent(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        connection.execute(
            "INSERT INTO koinon_content_folder_bindings VALUES('retained','mapping',"
            "'remote-folder','folder','remote-root','project','[\"remote-root\"]',1,now())"
        )
        for statement in (
            "UPDATE koinon_content_folder_bindings SET local_folder_id='source',revision=2",
            "UPDATE koinon_content_folder_bindings SET local_parent_id='workspace',revision=2",
            "UPDATE koinon_content_folder_bindings SET remote_folder_id='renamed-id',revision=2",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)
        connection.execute(
            "UPDATE koinon_content_folder_bindings SET remote_parent_id='moved-parent',"
            "ancestry_json='[\"moved-parent\"]',revision=2"
        )
        assert connection.execute(
            "SELECT local_folder_id,revision FROM koinon_content_folder_bindings"
        ).fetchone() == ("folder", 2)


async def test_unaccepted_run_and_substituted_provider_origin_are_rejected(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection, accepted=False)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            job_and_run(connection, "unaccepted")
        # A retained attempt cannot classify an asset under an unrelated provider principal.
        connection.execute(
            "INSERT INTO koinon_content_imports(id,tenant_id,mapping_id,mapping_revision,"
            "object_id,generation,intake_item_id,provider,external_subject,drive_id,"
            "remote_item_id,remote_version,source_id,asset_id,sha256,size_bytes,created_at) "
            "VALUES('substituted','retained','mapping',1,'origin',1,'item','google_drive',"
            "'unrelated-principal','drive','remote-file','v1','source','asset',%s,7,now())",
            ("d" * 64,),
        )
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "INSERT INTO koinon_content_imported_assets "
                "VALUES('asset','retained','source','substituted',now())"
            )


async def test_due_and_owner_lookups_use_indexes_with_retained_history(source_sessions, record_property):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        # Realistic history cardinality, with only a small due working set.
        connection.execute(
            "INSERT INTO koinon_content_mappings SELECT "
            "(jsonb_populate_record(NULL::koinon_content_mappings,"
            "to_jsonb(m)||jsonb_build_object('id','history-'||n,'root_id','root-'||n))).* "
            "FROM koinon_content_mappings m CROSS JOIN generate_series(1,10000) n WHERE "
            "m.id='mapping'"
        )
        connection.execute(
            (
                "INSERT INTO koinon_content_policies(id,tenant_id,owner,mapping_id,revision,"
                "mapping_revision,authority_sha256,policy_json,policy_sha256,root_ancestry_json,"
                "review_id,review_digest,review_expires_at,accepted_by,accepted_session_hash,"
                "accepted_operation_id,accepted_at,created_at) SELECT 'policy-'||n,'retained',%s,"
                "'history-'||n,1,1,repeat('a',64),'{}',repeat('b',64),"
                "json_build_array('root-'||n),'review-'||n,repeat('c',64),now()+interval '1 day',"
                "%s,repeat('d',64),gen_random_uuid()::text,now(),now() FROM generate_series(1,10000) n"
            ),
            (OWNER, OWNER),
        )
        connection.execute(
            "INSERT INTO koinon_content_policy_operations "
            "(id,tenant_id,owner,operation_id,action,mapping_id,policy_id,expected_policy_revision,"
            "result_policy_revision,payload_sha256,result_json,created_at) "
            "SELECT r.id,p.tenant_id,p.owner,p.accepted_operation_id,'apply',p.mapping_id,p.id,1,1,"
            "repeat('e',64),jsonb_build_object('schema','koinon.source-policy-operation.v1',"
            "'receipt_id',r.id,'operation_id',p.accepted_operation_id,'action','apply',"
            "'mapping_id',p.mapping_id,'policy_id',p.id,'expected_policy_revision',1,"
            "'result_policy_revision',1,'review_digest',p.review_digest,"
            "'review_expires_at',p.review_expires_at,'disposition','accepted'),now() "
            "FROM koinon_content_policies p CROSS JOIN LATERAL "
            "(SELECT gen_random_uuid()::text AS id WHERE p.id IS NOT NULL) r "
            "WHERE p.mapping_id LIKE 'history-%'"
        )
        connection.execute(
            "INSERT INTO koinon_content_sync_states SELECT 'history-'||n,'retained',"
            "'policy-'||n,n<=10,1,now()+CASE WHEN n<=10 THEN interval '-1 hour' ELSE "
            "interval '1 day' END,NULL,0,0,now() FROM generate_series(1,10000) n"
        )
        connection.execute(
            "INSERT INTO koinon_content_reader_sets SELECT 'retained','owner-'||n,0,now() "
            "FROM generate_series(1,10000) n"
        )
        connection.execute("ANALYZE koinon_content_sync_states")
        connection.execute("ANALYZE koinon_content_reader_sets")
        queries = {
            "due": (
                "SELECT mapping_id FROM koinon_content_sync_states WHERE enabled AND "
                "next_run_at<=now() ORDER BY next_run_at,tenant_id,mapping_id LIMIT 50"
            ),
            "owner": (
                "SELECT revision FROM koinon_content_reader_sets WHERE tenant_id='retained' AND "
                "owner='owner-9999'"
            ),
        }
        for name, query in queries.items():
            plan = connection.execute("EXPLAIN (ANALYZE,BUFFERS,FORMAT JSON) " + query).fetchone()[0][0]
            record_property(name + "_plan", plan)
            rendered = str(plan)
            assert "Seq Scan" not in rendered
            assert ("ix_content_sync_due" if name == "due" else "koinon_content_reader_sets_pkey") in rendered


@pytest.mark.parametrize(
    ("mutation", "behavior"),
    [
        ("snapshot_commit", test_reader_conflicting_put_and_abandoned_snapshot_cannot_advance),
        ("page_commit", test_page_work_and_checkpoint_are_atomic_and_work_survives_later_runs),
        ("generation", test_object_generation_cannot_regress_or_change_identity),
        ("root_overlap", test_accepted_policy_and_cross_account_overlap_are_serialized_per_tenant),
        ("folder_identity", test_folder_binding_preserves_identity_and_validates_tenant_parent),
        ("version_identity", test_import_marker_and_exact_receipt_are_immutable_and_roll_back_together),
        ("first_receipt", test_import_marker_and_exact_receipt_are_immutable_and_roll_back_together),
        ("accepted_run", test_unaccepted_run_and_substituted_provider_origin_are_rejected),
        ("provider_origin", test_unaccepted_run_and_substituted_provider_origin_are_rejected),
    ],
)
async def test_behavior_checks_detect_database_guard_removal(
    source_sessions, source_database, mutation, behavior, record_property
):
    """Mutation proof touches only a newly created synthetic database, never source files."""
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0].startswith("source_schema_")
        if mutation == "root_overlap":
            original = connection.execute(
                "SELECT pg_get_functiondef('koinon_content_guard_state()'::regprocedure)"
            ).fetchone()[0]
            assert "IF NEW.enabled AND" in original
            connection.execute(original.replace("IF NEW.enabled AND", "IF false AND", 1))
        else:
            guards = {
                "snapshot_commit": [
                    ("koinon_content_reader_selections", "complete_reader_snapshot"),
                    ("koinon_content_reader_operations", "complete_reader_snapshot"),
                ],
                "page_commit": [("koinon_content_sync_observations", "complete_page")],
                "generation": [("koinon_content_objects", "guard_sync_object")],
                "folder_identity": [("koinon_content_folder_bindings", "guard_folder")],
                "version_identity": [("koinon_content_imported_versions", "retain_rows")],
                "first_receipt": [("koinon_content_imports", "koinon_content_import_update")],
                "accepted_run": [("koinon_content_sync_runs", "guard_sync_run")],
                "provider_origin": [("koinon_content_imported_assets", "guard_marker")],
            }
            for table, trigger in guards[mutation]:
                connection.execute(
                    sql.SQL("DROP TRIGGER {} ON {}").format(sql.Identifier(trigger), sql.Identifier(table))
                )
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
        if mutation in {"version_identity", "first_receipt"}:
            await behavior(source_sessions, source_database)
        else:
            await behavior(source_sessions)
    record_property("detected_mutation", mutation)
