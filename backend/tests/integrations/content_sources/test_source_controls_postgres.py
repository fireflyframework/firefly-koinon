# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Real PostgreSQL retention and concurrency for source-control receipts."""

import psycopg
import pytest
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import job_and_run, policy, state

pytestmark = pytest.mark.integration


async def test_partial_run_is_terminal_without_rewriting_its_identity(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        job_and_run(connection, "run")
        connection.execute("UPDATE koinon_content_sync_runs SET status='partial' WHERE id='run'")
        assert connection.execute(
            "SELECT status,policy_id,mapping_revision FROM koinon_content_sync_runs WHERE id='run'"
        ).fetchone() == ("partial", "policy-mapping", 1)
        for statement in (
            "UPDATE koinon_content_sync_runs SET status='running' WHERE id='run'",
            "UPDATE koinon_content_sync_runs SET mapping_revision=2 WHERE id='run'",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)


def receipt(
    connection,
    identifier="receipt",
    *,
    action="pause",
    target=None,
    revision=1,
    operation=None,
    owner="issuer|alice",
    mapping="mapping",
    result_changes=None,
    payload="a" * 64,
):
    from uuid import uuid4

    from psycopg.types.json import Json

    operation = operation or str(uuid4())
    result = {
        "operation_id": operation,
        "receipt_id": identifier,
        "action": action,
        "control_revision": revision + 1,
        "disposition": "accepted",
    }
    result.update(result_changes or {})
    connection.execute(
        "INSERT INTO koinon_content_control_operations VALUES "
        "(%s,'retained',%s,%s,%s,%s,%s,%s,%s,%s,%s,now())",
        (
            identifier,
            owner,
            operation,
            action,
            mapping,
            target,
            revision,
            revision + 1,
            payload,
            Json(result),
        ),
    )
    return result


async def test_receipt_is_immutable_and_runtime_has_only_read_insert(source_sessions, source_database):
    import sqlalchemy as sa
    from psycopg import sql
    from test_source_migration_postgres import load

    from koinon.integrations.content_sources.sync_entities import SourceControlOperation

    _, uri = source_sessions
    _, role, engine = source_database
    table = "koinon_content_control_operations"
    actual = {c["name"]: c for c in sa.inspect(engine).get_columns(table)}
    assert set(actual) == set(SourceControlOperation.__table__.columns.keys())
    assert all(actual[c.name]["nullable"] == c.nullable for c in SourceControlOperation.__table__.columns)
    with psycopg.connect(uri) as connection:
        receipt(connection)
        for statement in (
            f"UPDATE {table} SET payload_sha256=repeat('b',64)",
            f"DELETE FROM {table}",
            f"TRUNCATE {table} CASCADE",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)
        connection.execute(
            sql.SQL("GRANT ALL ON {} TO {}").format(sql.Identifier(table), sql.Identifier(role))
        )
        connection.execute(
            sql.SQL("GRANT UPDATE(result_json) ON {} TO {}").format(
                sql.Identifier(table), sql.Identifier(role)
            )
        )
        load("deploy/provision_roles.py").grant_table(connection, table, role)
        assert connection.execute(
            "SELECT has_table_privilege(%s,%s,'SELECT'),has_table_privilege(%s,%s,'INSERT'),"
            "has_table_privilege(%s,%s,'UPDATE'),has_table_privilege(%s,%s,'DELETE'),"
            "has_table_privilege(%s,%s,'TRUNCATE'),has_column_privilege(%s,%s,'result_json','UPDATE')",
            (role, table) * 6,
        ).fetchone() == (True, True, False, False, False, False)
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        receipt(connection, "runtime", revision=2)
        assert connection.execute(f"SELECT count(*) FROM {table}").fetchone() == (2,)
        for statement in (
            f"UPDATE {table} SET result_json='{{}}'",
            f"DELETE FROM {table}",
            f"TRUNCATE {table}",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
                connection.execute(statement)


@pytest.mark.parametrize(
    "changes",
    [
        {"disposition": None},
        {"operation_id": None},
        {"receipt_id": None},
        {"action": None},
        {"control_revision": "2"},
        {"control_revision": 9},
        {"operation_id": "wrong"},
        {"status": None},
        {"status": "password"},
        {"title": "private title"},
        {"run_id": "x" * 65},
        {"disposition": "x" * 17000},
    ],
)
async def test_receipt_rejects_unsafe_or_inconsistent_result(source_sessions, changes):
    _, uri = source_sessions
    with (
        psycopg.connect(uri) as connection,
        pytest.raises(psycopg.errors.CheckViolation),
        connection.transaction(),
    ):
        receipt(connection, result_changes=changes)


async def test_operation_identity_and_authority_cannot_be_reused(source_sessions):
    from test_sync_schema_postgres import clone_mapping

    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        clone_mapping(connection, "other")
        result = receipt(connection)
        for kwargs, exception in (
            (
                {"action": "resume", "mapping": "other", "operation": result["operation_id"]},
                psycopg.errors.UniqueViolation,
            ),
            ({"owner": "issuer|bob", "revision": 2}, psycopg.errors.ForeignKeyViolation),
            ({"action": "cancel", "target": "missing", "revision": 2}, psycopg.errors.ForeignKeyViolation),
            ({"payload": "secret", "revision": 2}, psycopg.errors.CheckViolation),
            ({"operation": "not-a-uuid", "revision": 2}, psycopg.errors.CheckViolation),
            ({"revision": 1}, psycopg.errors.UniqueViolation),
        ):
            with pytest.raises(exception), connection.transaction():
                receipt(connection, "other-receipt", **kwargs)


async def test_cancellation_requires_exact_receipt_and_is_one_time(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        job_and_run(connection, "previous")
        connection.execute("UPDATE koinon_content_sync_runs SET status='failed' WHERE id='previous'")
        job_and_run(connection, "run")
        receipt(connection, "pause")
        receipt(connection, "wrong-run", action="cancel", target="previous", revision=2)
        receipt(connection, "cancel", action="cancel", target="run", revision=3)
        for identifier in ("missing", "pause", "wrong-run"):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    (
                        "UPDATE koinon_content_sync_runs SET "
                        "cancel_requested_at=now(),cancel_operation_id=%s WHERE id='run'"
                    ),
                    (identifier,),
                )
        connection.execute(
            "UPDATE koinon_content_sync_runs SET "
            "cancel_requested_at=now(),cancel_operation_id='cancel' WHERE id='run'"
        )
        marker = connection.execute(
            "SELECT cancel_requested_at,cancel_operation_id FROM koinon_content_sync_runs WHERE id='run'"
        ).fetchone()
        for assignments in (
            "cancel_operation_id=NULL,cancel_requested_at=NULL",
            "cancel_operation_id='wrong-run'",
            "cancel_requested_at=now()+interval '1 second'",
            "retry_of_run_id='previous'",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute("UPDATE koinon_content_sync_runs SET " + assignments + " WHERE id='run'")
        connection.execute(
            "UPDATE koinon_content_sync_runs SET page_sequence=1,status='cancelled' WHERE id='run'"
        )
        assert (
            connection.execute(
                "SELECT cancel_requested_at,cancel_operation_id FROM koinon_content_sync_runs WHERE id='run'"
            ).fetchone()
            == marker
        )
        receipt(connection, "retire", action="retire", revision=4)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "UPDATE koinon_content_sync_runs SET "
                "cancel_requested_at=now(),cancel_operation_id='retire' WHERE id='previous'"
            )
        job_and_run(connection, "next")
        connection.execute(
            "UPDATE koinon_content_sync_runs SET "
            "cancel_requested_at=now(),cancel_operation_id='retire' WHERE id='next'"
        )
        assert connection.execute(
            "SELECT cancel_operation_id FROM koinon_content_sync_runs WHERE id='next'"
        ).fetchone() == ("retire",)


def retry_run(connection, identifier, predecessor, *, kind="retry"):
    from psycopg.types.json import Json

    connection.execute(
        (
            "INSERT INTO lattice_jobs(id,tenant_id,resource_id,kind,idempotency_key,payload_h"
            "ash,payload,status,attempts,max_attempts,progress,available_at,created_at,update"
            "d_at) "
            "VALUES(%s,'retained','mapping','content.source.reconcile',%s,%s,'{}','queued',0,"
            "3,0,now(),now(),now())"
        ),
        ("job-" + identifier, identifier, "a" * 64),
    )
    connection.execute(
        "INSERT INTO koinon_content_sync_runs SELECT (jsonb_populate_record(NULL::koinon_content_sync_runs,"
        "to_jsonb(r)||%s::jsonb)).* FROM koinon_content_sync_runs r WHERE id='previous'",
        (
            Json(
                {
                    "id": identifier,
                    "job_id": "job-" + identifier,
                    "operation_id": identifier,
                    "trigger_kind": kind,
                    "status": "queued",
                    "retry_of_run_id": predecessor,
                }
            ),
        ),
    )


@pytest.mark.parametrize("status", ["failed", "partial", "reconnect_required", "cancelled"])
async def test_retry_preserves_eligible_predecessor_and_rejects_rebinding(source_sessions, status):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        job_and_run(connection, "previous")
        connection.execute("UPDATE koinon_content_sync_runs SET status=%s WHERE id='previous'", (status,))
        retry_run(connection, "retry", "previous")
        assert connection.execute(
            "SELECT retry_of_run_id,status FROM koinon_content_sync_runs WHERE id='retry'"
        ).fetchone() == ("previous", "queued")
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("UPDATE koinon_content_sync_runs SET retry_of_run_id=NULL WHERE id='retry'")


@pytest.mark.parametrize(
    "status,predecessor,kind",
    [
        ("queued", "previous", "retry"),
        ("succeeded", "previous", "retry"),
        ("failed", None, "retry"),
        ("failed", "missing", "retry"),
        ("failed", "retry", "retry"),
        ("failed", "previous", "manual"),
    ],
)
async def test_retry_rejects_ineligible_or_invented_history(source_sessions, status, predecessor, kind):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        job_and_run(connection, "previous")
        connection.execute("UPDATE koinon_content_sync_runs SET status=%s WHERE id='previous'", (status,))
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            retry_run(connection, "retry", predecessor, kind=kind)


async def test_control_cas_serializes_and_rollback_leaves_no_receipt(source_sessions):
    import asyncio

    from test_source_concurrency_postgres import wait_for_blocked_connection

    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        with pytest.raises(RuntimeError), connection.transaction():
            receipt(connection, "rolled-back")
            connection.execute("UPDATE koinon_content_sync_states SET revision=2 WHERE mapping_id='mapping'")
            raise RuntimeError("abort the control transaction")
        assert connection.execute("SELECT count(*) FROM koinon_content_control_operations").fetchone() == (0,)
        assert connection.execute("SELECT revision FROM koinon_content_sync_states").fetchone() == (1,)
    first = await psycopg.AsyncConnection.connect(uri)
    second = await psycopg.AsyncConnection.connect(uri, application_name="control-cas")
    task = None
    try:
        query = (
            "UPDATE koinon_content_sync_states SET revision=2 WHERE mapping_id='mapping' AND "
            "revision=1 RETURNING revision"
        )
        assert await (await first.execute(query)).fetchone() == (2,)
        task = asyncio.create_task(second.execute(query))
        await wait_for_blocked_connection(uri, "control-cas")
        await first.commit()
        assert await (await task).fetchone() is None
        await second.commit()
    finally:
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await second.close()
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            "SELECT revision FROM koinon_content_mappings WHERE id='mapping'"
        ).fetchone() == (1,)


@pytest.fixture
async def legacy_sessions(source_database, monkeypatch):
    import test_source_concurrency_postgres as concurrency
    from alembic import command
    from test_source_migration_postgres import ROOT, load

    def upgrade_to_46(engine):
        with engine.connect() as connection:
            config = load("deploy/migrate.py").history_config(
                "native", ROOT / "deploy/migrations/native_versions", connection
            )
            command.upgrade(config, "koinon_0046_source_sync")
            connection.commit()

    monkeypatch.setattr(concurrency, "upgrade_sources", upgrade_to_46)
    async for sessions in source_sessions.__wrapped__(source_database):
        yield sessions


async def test_upgrade_from_46_retains_history_without_invented_retry_lineage(
    legacy_sessions, source_database
):
    from test_source_migration_postgres import upgrade_sources

    _, uri = legacy_sessions
    _, _, engine = source_database
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        job_and_run(connection, "previous")
        connection.execute("UPDATE koinon_content_sync_runs SET status='failed' WHERE id='previous'")
        job_and_run(connection, "legacy")
        # The historical trigger accepted unlinked retry inserts. Reproduce an old
        # record through INSERT, preserving its immutable trigger_kind afterwards.
        connection.execute("UPDATE koinon_content_sync_runs SET status='failed' WHERE id='legacy'")
        connection.execute(
            "INSERT INTO lattice_jobs SELECT "
            '(jsonb_populate_record(NULL::lattice_jobs,to_jsonb(j)||\'{"id":"job-old-retry","i'
            "dempotency_key\":\"old-retry\"}')).* FROM lattice_jobs j WHERE id='job-legacy'"
        )
        connection.execute(
            "INSERT INTO koinon_content_sync_runs SELECT "
            '(jsonb_populate_record(NULL::koinon_content_sync_runs,to_jsonb(r)||\'{"id":"old-r'
            'etry","job_id":"job-old-retry","operation_id":"old-retry","trigger_kind":"retry"'
            "}')).* FROM koinon_content_sync_runs r WHERE id='legacy'"
        )
        before = connection.execute(
            "SELECT id,to_jsonb(r) FROM koinon_content_sync_runs r ORDER BY id"
        ).fetchall()
    upgrade_sources(engine)
    with psycopg.connect(uri) as connection:
        after = connection.execute(
            "SELECT id,to_jsonb(r)-ARRAY['cancel_requested_at','cancel_operation_id','retry_o"
            "f_run_id'] FROM koinon_content_sync_runs r ORDER BY id"
        ).fetchall()
        assert after == before
        assert connection.execute(
            "SELECT cancel_requested_at,cancel_operation_id,retry_of_run_id FROM "
            "koinon_content_sync_runs WHERE id='old-retry'"
        ).fetchone() == (None, None, None)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            retry_run(connection, "new-retry", None)
        assert connection.execute("SELECT version_num FROM koinon_native_version").fetchone() == (
            "koinon_0047_source_controls",
        )


async def test_receipt_lookup_and_retry_lineage_have_indexed_plans(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        connection.execute("""
            INSERT INTO koinon_content_control_operations
            SELECT 'receipt-'||n,'retained','issuer|alice',md5(n::text)::uuid::text,
              'pause','mapping',NULL,n,n+1,repeat('a',64),
              json_build_object('operation_id',md5(n::text)::uuid::text,'receipt_id','receipt-'||n,
                'action','pause','control_revision',n+1,'disposition','paused'),now()
            FROM generate_series(1,5000) n
        """)
        connection.execute("ANALYZE koinon_content_control_operations")
        plan = connection.execute(
            "EXPLAIN (FORMAT JSON, ANALYZE) SELECT result_json FROM "
            "koinon_content_control_operations WHERE tenant_id='retained' AND "
            "owner='issuer|alice' AND operation_id=md5('4200')::uuid::text"
        ).fetchone()[0][0]["Plan"]
        assert plan["Node Type"] == "Index Scan"
        assert plan["Index Name"] == "uq_content_control_operation"
        assert plan["Actual Rows"] == 1
        policy(connection)
        state(connection)
        job_and_run(connection, "previous")
        connection.execute("UPDATE koinon_content_sync_runs SET status='failed' WHERE id='previous'")
        connection.execute("""
            INSERT INTO lattice_jobs
            SELECT (jsonb_populate_record(NULL::lattice_jobs, to_jsonb(j)||jsonb_build_object(
              'id','job-history-'||n,'idempotency_key','history-'||n))).*
            FROM lattice_jobs j CROSS JOIN generate_series(1,5000) n WHERE j.id='job-previous'
        """)
        connection.execute("""
            INSERT INTO koinon_content_sync_runs
            SELECT (jsonb_populate_record(NULL::koinon_content_sync_runs, to_jsonb(r)||jsonb_build_object(
              'id','history-'||n,'job_id','job-history-'||n,'operation_id','history-'||n))).*
            FROM koinon_content_sync_runs r CROSS JOIN generate_series(1,5000) n WHERE r.id='previous'
        """)
        retry_run(connection, "retry", "previous")
        connection.execute("ANALYZE koinon_content_sync_runs")
        retry_plan = connection.execute(
            "EXPLAIN (FORMAT JSON, ANALYZE) SELECT id FROM koinon_content_sync_runs "
            "WHERE tenant_id='retained' AND mapping_id='mapping' AND retry_of_run_id='previous'"
        ).fetchone()[0][0]["Plan"]
        assert retry_plan["Node Type"] == "Index Scan"
        assert retry_plan["Index Name"] == "ix_content_run_retry"
        assert retry_plan["Actual Rows"] == 1
        for name in ("ix_content_run_retry", "ix_content_control_run"):
            definition = connection.execute(
                "SELECT indexdef FROM pg_indexes WHERE indexname=%s", (name,)
            ).fetchone()[0]
            assert "tenant_id, mapping_id" in definition
            assert "IS NOT NULL" in definition


@pytest.mark.parametrize("mutation", ["receipt_retention", "safe_result", "cancel_receipt", "retry_lineage"])
async def test_control_behavior_detects_missing_database_guards(
    source_sessions, source_database, mutation, record_property
):
    """Remove one guard only in this test's unique synthetic database."""
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0].startswith("source_schema_")
        if mutation == "receipt_retention":
            connection.execute("DROP TRIGGER retain_rows ON koinon_content_control_operations")
        elif mutation == "safe_result":
            connection.execute(
                "ALTER TABLE koinon_content_control_operations DROP CONSTRAINT ck_content_control_result"
            )
        else:
            original = connection.execute(
                "SELECT pg_get_functiondef('koinon_content_guard_run()'::regprocedure)"
            ).fetchone()[0]
            if mutation == "cancel_receipt":
                needle = "IF cancellation.id IS NULL OR NOT ("
                replacement = "IF false AND (cancellation.id IS NULL OR NOT ("
                assert needle in original
                original = original.replace(needle, replacement, 1).replace(
                    "cancellation.target_run_id IS NULL)) THEN",
                    "cancellation.target_run_id IS NULL))) THEN",
                    1,
                )
            else:
                needle = "IF NEW.trigger_kind='retry' THEN"
                assert needle in original
                original = original.replace(needle, "IF false THEN", 1)
            connection.execute(original)
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
        if mutation == "receipt_retention":
            await test_receipt_is_immutable_and_runtime_has_only_read_insert(source_sessions, source_database)
        elif mutation == "safe_result":
            await test_receipt_rejects_unsafe_or_inconsistent_result(source_sessions, {"disposition": None})
        elif mutation == "cancel_receipt":
            # Existing unrelated receipts satisfy the FK; only the semantic guard
            # rejects marking this run with a pause receipt.
            with psycopg.connect(uri) as connection:
                policy(connection)
                state(connection)
                job_and_run(connection, "run")
                receipt(connection, "pause")
                with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                    connection.execute(
                        "UPDATE koinon_content_sync_runs SET cancel_requested_at=now(),"
                        "cancel_operation_id='pause' WHERE id='run'"
                    )
        else:
            await test_retry_rejects_ineligible_or_invented_history(source_sessions, "failed", None, "retry")
    record_property("detected_control_mutation", mutation)


async def test_resuming_expansion_retains_receipts_and_completed_cancellation(
    source_sessions, source_database
):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from test_source_migration_postgres import load

    _, uri = source_sessions
    _, _, engine = source_database
    with psycopg.connect(uri) as connection:
        policy(connection)
        state(connection)
        job_and_run(connection, "run")
        receipt(connection, "cancel", action="cancel", target="run")
        connection.execute(
            "UPDATE koinon_content_sync_runs SET cancel_requested_at=now(),"
            "cancel_operation_id='cancel',status='cancelled' WHERE id='run'"
        )
        before = connection.execute("SELECT to_jsonb(r) FROM koinon_content_sync_runs r").fetchall()
        saved = connection.execute("SELECT to_jsonb(r) FROM koinon_content_control_operations r").fetchall()
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        with context.begin_transaction(), Operations.context(context):
            load("deploy/migrations/native_versions/0047_source_controls.py").upgrade()
        connection.commit()
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT to_jsonb(r) FROM koinon_content_sync_runs r").fetchall() == before
        assert (
            connection.execute("SELECT to_jsonb(r) FROM koinon_content_control_operations r").fetchall()
            == saved
        )
        assert connection.execute(
            "SELECT bool_and(convalidated) FROM pg_constraint WHERE "
            "conrelid='koinon_content_sync_runs'::regclass"
        ).fetchone() == (True,)
