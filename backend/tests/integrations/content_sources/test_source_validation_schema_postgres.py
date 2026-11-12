# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Transient validation bounds and scheduler claims on real PostgreSQL."""

import asyncio
from datetime import UTC, datetime, timedelta
from typing import LiteralString, cast
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_concurrency_postgres import wait_for_blocked_connection
from test_source_migration_postgres import ROOT, load, upgrade_sources
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import policy
from test_sync_schema_postgres import (
    test_due_and_owner_lookups_use_indexes_with_retained_history as seed_scheduler_history,
)

pytestmark = pytest.mark.integration


def test_model_schema_keeps_sqlite_http_fixtures_usable():
    from koinon.integrations.content_sources.mapping_validation_entities import SourceMappingValidation
    from koinon.integrations.content_sources.sync_entities import SourceSyncState

    engine = sa.create_engine("sqlite://")
    try:
        for entity in (SourceMappingValidation, SourceSyncState):
            cast(sa.Table, entity.__table__).create(engine)
        assert set(sa.inspect(engine).get_table_names()) == {
            "koinon_content_mapping_validations",
            "koinon_content_sync_states",
        }
    finally:
        engine.dispose()


def test_transient_validation_and_scheduler_schema_exists(source_database):
    _, _, engine = source_database
    upgrade_sources(engine)
    inspector = sa.inspect(engine)
    assert {
        "koinon_content_mapping_validations",
        "koinon_content_mapping_validation_entries",
    } <= set(inspector.get_table_names())
    assert {
        "scheduler_claim_token",
        "scheduler_claim_until",
        "scheduler_last_attempt_at",
        "scan_observed_count",
        "scan_max_items",
    } <= {column["name"] for column in inspector.get_columns("koinon_content_sync_states")}


def begin(connection, **changes):
    now = datetime.now(UTC)
    values = {
        "id": uuid4(),
        "tenant_id": "retained",
        "owner": "issuer|alice",
        "operation_id": uuid4(),
        "session_hash": "a" * 64,
        "request_sha256": "b" * 64,
        "request_ciphertext": b"encrypted-selection",
        "connection_id": "connection",
        "connection_revision": 1,
        "authority_sha256": "c" * 64,
        "root_kind": "folder",
        "root_proof_sha256": "d" * 64,
        "root_proof_ciphertext": b"encrypted-root",
        "scan_max_items": 100,
        "reserved_bytes": 100 * 16384 + 8388608,
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(hours=8),
        **changes,
    }
    has_capture = connection.execute(
        "SELECT EXISTS(SELECT 1 FROM information_schema.columns WHERE table_schema='public' "
        "AND table_name='koinon_content_mapping_validations' AND column_name='root_captured')"
    ).fetchone()[0]
    proof = None
    if has_capture and values["root_kind"] is not None:
        proof = {key: values[key] for key in ("root_kind", "root_proof_sha256", "root_proof_ciphertext")}
        values.update(root_kind=None, root_proof_sha256=None, root_proof_ciphertext=None)
    connection.execute(
        sql.SQL("INSERT INTO koinon_content_mapping_validations ({}) VALUES ({})").format(
            sql.SQL(",").join(map(sql.Identifier, values)),
            sql.SQL(",").join(sql.Placeholder() for _ in values),
        ),
        tuple(values.values()),
    )
    if proof is not None:
        advance(
            connection,
            values["id"],
            root_captured=True,
            checkpoint_ciphertext=b"encrypted-start",
            **proof,
        )
    return values["id"]


def entry(connection, validation, *, item="file", sequence=0, payload=b"encrypted-name", tenant="retained"):
    connection.execute(
        "INSERT INTO koinon_content_mapping_validation_entries(tenant_id,validation_id,item_id,sequence,"
        "fingerprint_sha256,candidate_ciphertext,destination_key_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s)",
        (tenant, validation, item, sequence, "e" * 64, payload, "f" * 64),
    )


def advance(connection, validation, **changes):
    connection.execute(
        sql.SQL("UPDATE koinon_content_mapping_validations SET {},revision=revision+1 WHERE id=%s").format(
            sql.SQL(",").join(sql.SQL("{}=%s").format(sql.Identifier(key)) for key in changes)
        ),
        (*changes.values(), validation),
    )


def seal(connection, validation):
    advance(
        connection,
        validation,
        state="verifying",
        enumeration_complete=True,
        raw_observed_count=1,
        eligible_count=1,
    )
    connection.execute(
        "UPDATE koinon_content_mapping_validation_entries SET verified=true WHERE validation_id=%s",
        (validation,),
    )
    advance(connection, validation, state="checking_changes", verification_position=1)
    advance(
        connection,
        validation,
        state="complete",
        manifest_sha256="1" * 64,
        checkpoint_ciphertext=b"encrypted-terminal",
    )


def cleaning(connection, validation):
    advance(
        connection,
        validation,
        state="cleaning",
        request_ciphertext=None,
        root_proof_ciphertext=None,
        checkpoint_ciphertext=None,
        walk_ciphertext=None,
        cleanup_reason="abandoned",
    )


async def test_validation_schema_matches_models_and_scoped_foreign_keys(source_sessions, source_database):
    _, uri = source_sessions
    _, _, engine = source_database
    from koinon.integrations.content_sources.mapping_validation_entities import (
        SourceMappingValidation,
        SourceMappingValidationEntry,
    )

    inspector = sa.inspect(engine)
    for entity in (SourceMappingValidation, SourceMappingValidationEntry):
        actual = {column["name"]: column for column in inspector.get_columns(entity.__tablename__)}
        assert set(actual) == set(entity.__table__.columns.keys())
        assert all(actual[column.name]["nullable"] == column.nullable for column in entity.__table__.columns)
        assert {index.name for index in cast(sa.Table, entity.__table__).indexes} <= {
            index["name"] for index in inspector.get_indexes(entity.__tablename__)
        }
    with psycopg.connect(uri) as connection:
        validation = begin(connection)
        with pytest.raises(psycopg.errors.ForeignKeyViolation), connection.transaction():
            entry(connection, validation, tenant="foreign")
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            row = connection.execute(
                "SELECT operation_id FROM koinon_content_mapping_validations WHERE id=%s", (validation,)
            ).fetchone()
            assert row is not None
            begin(connection, operation_id=row[0])


@pytest.mark.parametrize(
    "changes",
    [
        {"owner": "foreign"},
        {"session_hash": "changed"},
        {"request_sha256": "changed"},
        {"scan_max_items": 200},
        {"expires_at": datetime(2099, 1, 1, tzinfo=UTC)},
        {"request_ciphertext": b"substituted"},
    ],
)
async def test_validation_cannot_rebind_identity_selection_or_bounds(source_sessions, changes):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        validation = begin(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            advance(connection, validation, **changes)


async def test_validation_capacity_reserves_full_manifest_and_serializes_concurrent_begin(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as writer:
        begin(writer)
        writer.commit()
        begin(writer)
        application = "validation-admission-" + uuid4().hex
        with psycopg.connect(uri, application_name=application) as other:
            waiter = asyncio.create_task(asyncio.to_thread(begin, other))
            try:
                await wait_for_blocked_connection(uri, application)
                assert not waiter.done()
            finally:
                writer.commit()
            with pytest.raises(psycopg.errors.CheckViolation, match="CAPACITY"):
                await waiter
            other.rollback()
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="SOURCE_VALIDATION_CAPACITY"),
            writer.transaction(),
        ):
            begin(writer)
        assert writer.execute("SELECT count(*) FROM koinon_content_mapping_validations").fetchone() == (2,)


async def test_validation_byte_budget_and_actual_encrypted_bounds(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        validation = begin(connection, max_retained_bytes_per_tenant=100 * 16384 + 8388608)
        with pytest.raises(psycopg.errors.CheckViolation, match="CAPACITY"), connection.transaction():
            begin(connection, max_retained_bytes_per_tenant=100 * 16384 + 8388608)
        with pytest.raises(psycopg.errors.CheckViolation, match="payload bound"), connection.transaction():
            entry(connection, validation, payload=b"x" * 16384)
        entry(connection, validation, payload=b"x" * 15000)
        stored = connection.execute(
            "SELECT payload_bytes FROM koinon_content_mapping_validation_entries"
        ).fetchone()
        assert stored is not None and stored[0] > 15000
        with pytest.raises(psycopg.errors.CheckViolation, match="payload bound"), connection.transaction():
            advance(connection, validation, walk_ciphertext=b"x" * 8388608)


async def test_validation_bound_counts_duplicates_and_cannot_seal_partial_or_mutate_seal(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        validation = begin(connection)
        entry(connection, validation)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            advance(connection, validation, state="complete", manifest_sha256="1" * 64)
        seal(connection, validation)
        for changes in (
            {"manifest_sha256": "2" * 64},
            {"checkpoint_ciphertext": b"new"},
            {"raw_observed_count": 2},
        ):
            with pytest.raises(psycopg.errors.CheckViolation, match="immutable"), connection.transaction():
                advance(connection, validation, **changes)
        with pytest.raises(psycopg.errors.CheckViolation, match="frozen"), connection.transaction():
            entry(connection, validation, item="late", sequence=1)
        second = begin(connection)
        advance(
            connection,
            second,
            raw_observed_count=101,
            state="blocked",
            reason_code="SOURCE_SCAN_LIMIT_EXCEEDED",
        )
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            advance(connection, second, raw_observed_count=1)
        assert connection.execute(
            "SELECT raw_observed_count FROM koinon_content_mapping_validations WHERE id=%s", (second,)
        ).fetchone() == (101,)


async def test_cleanup_keeps_capacity_and_recovery_until_payload_gone(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        validation = begin(connection, max_active_per_tenant=1, max_active_per_owner=1)
        entry(connection, validation)
        cleaning(connection, validation)
        with pytest.raises(psycopg.errors.CheckViolation, match="CAPACITY"), connection.transaction():
            begin(connection, max_active_per_tenant=1, max_active_per_owner=1)
        with pytest.raises(psycopg.errors.CheckViolation, match="child cleanup"), connection.transaction():
            advance(connection, validation, state="abandoned", payload_released_at=datetime.now(UTC))
        with pytest.raises(psycopg.errors.CheckViolation, match="live claim"), connection.transaction():
            connection.execute(
                "DELETE FROM koinon_content_mapping_validation_entries WHERE validation_id=%s", (validation,)
            )
        connection.execute(
            "UPDATE koinon_content_mapping_validations SET cleanup_claim_token=%s,"
            "cleanup_claim_until=clock_timestamp()+interval '10 seconds',"
            "cleanup_last_attempt_at=clock_timestamp() WHERE id=%s",
            (uuid4(), validation),
        )
        connection.execute(
            "DELETE FROM koinon_content_mapping_validation_entries WHERE validation_id=%s", (validation,)
        )
        advance(connection, validation, state="abandoned", payload_released_at=datetime.now(UTC))
        row = connection.execute(
            "SELECT reserved_bytes,payload_bytes FROM koinon_content_mapping_validations WHERE id=%s",
            (validation,),
        ).fetchone()
        assert row is not None and row[0] == row[1] and row[0] < 8192
        begin(connection, max_active_per_tenant=1, max_active_per_owner=1)
        with pytest.raises(psycopg.errors.CheckViolation, match="retained"), connection.transaction():
            connection.execute("DELETE FROM koinon_content_mapping_validations WHERE id=%s", (validation,))


async def test_scheduler_maintenance_preserves_control_revision_and_binds_claim(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        connection.execute(
            "INSERT INTO koinon_content_sync_states(mapping_id,tenant_id,accepted_policy_id,enabled,revision,"
            "next_run_at,scan_generation,last_complete_scan_generation,updated_at) "
            "VALUES('mapping','retained','policy-mapping',true,1,now(),0,0,now())"
        )
        connection.execute(
            "UPDATE koinon_content_sync_states SET scheduler_claim_token=%s,"
            "scheduler_claim_until=clock_timestamp()+interval '420 seconds',"
            "scheduler_claim_policy_id=accepted_policy_id,scheduler_claim_control_revision=revision,"
            "scheduler_claim_occurrence_at=next_run_at,scheduler_last_attempt_at=clock_timestamp()",
            (uuid4(),),
        )
        assert connection.execute("SELECT revision FROM koinon_content_sync_states").fetchone() == (1,)
        for statement in (
            "UPDATE koinon_content_sync_states SET scheduler_claim_control_revision=2",
            "UPDATE koinon_content_sync_states SET scheduler_claim_until=NULL",
            "UPDATE koinon_content_sync_states SET enabled=false",
            "UPDATE koinon_content_sync_states SET scheduler_failure_count=-1",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)


async def test_raw_scan_counter_cannot_reset_or_complete_unknown_or_over_limit(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        policy(connection)
        connection.execute(
            "INSERT INTO koinon_content_sync_states(mapping_id,tenant_id,accepted_policy_id,enabled,revision,"
            "scan_generation,last_complete_scan_generation,updated_at) "
            "VALUES('mapping','retained','policy-mapping',true,1,1,0,now())"
        )
        with (
            pytest.raises(psycopg.errors.CheckViolation, match="captured work bound"),
            connection.transaction(),
        ):
            connection.execute(
                "UPDATE koinon_content_sync_states SET revision=revision+1,last_complete_scan_generation=1"
            )
        connection.execute(
            "UPDATE koinon_content_sync_states SET revision=revision+1,"
            "scan_max_items=100,scan_observed_count=100"
        )
        for statement in (
            "UPDATE koinon_content_sync_states SET revision=revision+1,scan_observed_count=0",
            "UPDATE koinon_content_sync_states SET revision=revision+1,scan_max_items=200",
            "UPDATE koinon_content_sync_states SET revision=revision+1,"
            "scan_observed_count=101,last_complete_scan_generation=1",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)
        connection.execute(
            "UPDATE koinon_content_sync_states SET revision=revision+1,last_complete_scan_generation=1"
        )
        connection.execute(
            "UPDATE koinon_content_sync_states SET revision=revision+1,"
            "scan_generation=2,scan_observed_count=0,scan_max_items=200"
        )
        assert connection.execute(
            "SELECT scan_generation,scan_observed_count,scan_max_items FROM koinon_content_sync_states"
        ).fetchone() == (2, 0, 200)


async def test_runtime_role_can_prepare_and_clean_but_cannot_destroy_recovery(
    source_sessions, source_database
):
    _, uri = source_sessions
    _, role, _ = source_database
    roles = load("deploy/provision_roles.py")
    with psycopg.connect(uri) as owner:
        for table in ("koinon_content_mapping_validations", "koinon_content_mapping_validation_entries"):
            roles.grant_table(owner, table, role)
            assert owner.execute(
                "SELECT has_table_privilege(%s,%s,'TRUNCATE')", (role, table)
            ).fetchone() == (False,)
    with psycopg.connect(uri, user=role) as connection:
        validation = begin(connection)
        entry(connection, validation)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute("DELETE FROM koinon_content_mapping_validations WHERE id=%s", (validation,))
        cleaning(connection, validation)
        with pytest.raises(psycopg.errors.CheckViolation, match="reservation"), connection.transaction():
            advance(connection, validation, reserved_bytes=1)
        expired_claim = uuid4()
        connection.execute(
            "UPDATE koinon_content_mapping_validations SET cleanup_claim_token=%s,"
            "cleanup_claim_until=clock_timestamp()-interval '1 second' WHERE id=%s",
            (expired_claim, validation),
        )
        with pytest.raises(psycopg.errors.CheckViolation, match="live claim"), connection.transaction():
            connection.execute(
                "DELETE FROM koinon_content_mapping_validation_entries WHERE validation_id=%s", (validation,)
            )
        new_claim = uuid4()
        connection.execute(
            "UPDATE koinon_content_mapping_validations SET cleanup_claim_token=%s,"
            "cleanup_claim_until=clock_timestamp()+interval '10 seconds' WHERE id=%s",
            (new_claim, validation),
        )
        assert (
            connection.execute(
                "UPDATE koinon_content_mapping_validations "
                "SET cleanup_claim_token=NULL,cleanup_claim_until=NULL "
                "WHERE id=%s AND cleanup_claim_token=%s RETURNING id",
                (validation, expired_claim),
            ).fetchone()
            is None
        )
        connection.execute(
            "DELETE FROM koinon_content_mapping_validation_entries WHERE validation_id=%s", (validation,)
        )
        advance(connection, validation, state="abandoned", payload_released_at=datetime.now(UTC))
        assert connection.execute(
            "SELECT state FROM koinon_content_mapping_validations WHERE id=%s", (validation,)
        ).fetchone() == ("abandoned",)


async def test_cleaned_creation_tombstone_still_counts_toward_record_cap(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        limits = {"max_active_per_tenant": 1, "max_active_per_owner": 1, "max_records_per_tenant": 1}
        validation = begin(connection, **limits)
        cleaning(connection, validation)
        advance(connection, validation, state="abandoned", payload_released_at=datetime.now(UTC))
        with pytest.raises(psycopg.errors.CheckViolation, match="CAPACITY"), connection.transaction():
            begin(connection, **limits)
        assert (
            connection.execute(
                "SELECT operation_id FROM koinon_content_mapping_validations WHERE id=%s", (validation,)
            ).fetchone()
            is not None
        )


def test_interrupted_expansion_rolls_back_then_retries_without_old_row_changes(source_database):
    _, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0052_publication_baseline")
        connection.commit()
        before = connection.exec_driver_sql("SELECT to_jsonb(t) FROM lattice_tenants t").all()
        command.upgrade(config, "head")
        connection.rollback()
        assert (
            connection.exec_driver_sql(
                "SELECT to_regclass('koinon_content_mapping_validations')"
            ).scalar_one()
            is None
        )
        assert (
            connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar_one()
            == "koinon_0052_publication_baseline"
        )
        connection.commit()
        command.upgrade(config, "head")
        connection.commit()
        assert connection.exec_driver_sql("SELECT to_jsonb(t) FROM lattice_tenants t").all() == before
        assert (
            connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar_one()
            == "koinon_0055_validation_root"
        )


async def test_validation_scoped_and_cleanup_queries_use_indexes_with_large_history(
    source_sessions, record_property
):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        validation = begin(connection, root_kind=None, root_proof_sha256=None, root_proof_ciphertext=None)
        connection.execute("""INSERT INTO lattice_tenants(id,name,created_at)
          SELECT 'validation-tenant-'||n,'Synthetic',now() FROM generate_series(1,10000) n""")
        connection.execute("""INSERT INTO koinon_content_connections
          SELECT (jsonb_populate_record(NULL::koinon_content_connections,to_jsonb(c)||
            jsonb_build_object('id','validation-connection-'||n,'tenant_id','validation-tenant-'||n))).*
          FROM koinon_content_connections c CROSS JOIN generate_series(1,10000) n WHERE c.id='connection'""")
        connection.execute(
            """INSERT INTO koinon_content_mapping_validations
          SELECT (jsonb_populate_record(NULL::koinon_content_mapping_validations,to_jsonb(v)||
            jsonb_build_object('id',gen_random_uuid(),'operation_id',gen_random_uuid(),
              'tenant_id','validation-tenant-'||n,'connection_id','validation-connection-'||n))).*
          FROM koinon_content_mapping_validations v CROSS JOIN generate_series(1,10000) n WHERE v.id=%s""",
            (validation,),
        )
        connection.execute("""UPDATE koinon_content_mapping_validations SET
          root_captured=true,root_kind='folder',root_proof_sha256=repeat('d',64),
          root_proof_ciphertext='encrypted-root',checkpoint_ciphertext='encrypted-start',
          revision=revision+1""")
        connection.execute("""INSERT INTO koinon_content_mapping_validation_entries
          (tenant_id,validation_id,item_id,sequence,fingerprint_sha256,candidate_ciphertext,destination_key_sha256)
          SELECT tenant_id,id,'file',0,repeat('e',64),'encrypted',repeat('f',64)
          FROM koinon_content_mapping_validations""")
        cleaning(connection, validation)
        connection.execute("ANALYZE koinon_content_mapping_validations")
        connection.execute("ANALYZE koinon_content_mapping_validation_entries")
        queries = (
            (
                "owner",
                "SELECT id FROM koinon_content_mapping_validations "
                "WHERE tenant_id='retained' AND owner='issuer|alice'",
                (),
            ),
            (
                "cleanup",
                "SELECT id FROM koinon_content_mapping_validations WHERE state='cleaning' "
                "ORDER BY cleanup_last_attempt_at NULLS FIRST,tenant_id,id LIMIT 1",
                (),
            ),
            (
                "entries",
                "SELECT item_id FROM koinon_content_mapping_validation_entries "
                "WHERE tenant_id='retained' AND validation_id=%s ORDER BY sequence LIMIT 25",
                (validation,),
            ),
        )
        for name, query, params in queries:
            result = connection.execute(
                cast(LiteralString, "EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON) " + query), params
            ).fetchone()
            assert result is not None
            plan = result[0][0]
            record_property(name + "_plan", plan)
            pending = [plan["Plan"]]
            nodes = []
            while pending:
                node = pending.pop()
                nodes.append(node)
                pending.extend(node.get("Plans", []))
            assert plan["Plan"]["Actual Rows"] == 1
            assert any("Index" in node["Node Type"] for node in nodes)
            assert all(node["Node Type"] != "Seq Scan" for node in nodes)


async def test_scheduler_fair_order_uses_partial_index(source_sessions, record_property):
    await seed_scheduler_history(source_sessions, record_property)
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        result = connection.execute("""EXPLAIN(ANALYZE,BUFFERS,FORMAT JSON)
          SELECT mapping_id FROM koinon_content_sync_states
          WHERE enabled AND next_run_at IS NOT NULL AND next_run_at<=now()
            AND (scheduler_retry_not_before IS NULL OR scheduler_retry_not_before<=now())
            AND (scheduler_claim_until IS NULL OR scheduler_claim_until<=now())
          ORDER BY scheduler_last_attempt_at NULLS FIRST,next_run_at,tenant_id,mapping_id LIMIT 10
        """).fetchone()
        assert result is not None
        plan = result[0][0]
        record_property("scheduler_fair_plan", plan)
        assert plan["Plan"]["Actual Rows"] == 10
        pending = [plan["Plan"]]
        nodes = []
        while pending:
            node = pending.pop()
            nodes.append(node)
            pending.extend(node.get("Plans", []))
        assert any("Index" in node["Node Type"] for node in nodes), plan
        assert all(node["Node Type"] != "Seq Scan" for node in nodes), plan
        assert (
            sum(
                (node["Actual Rows"] + node.get("Rows Removed by Filter", 0)) * node["Actual Loops"]
                for node in nodes
            )
            <= 100
        ), plan
        assert all(
            node.get("Temp Read Blocks", 0) == node.get("Temp Written Blocks", 0) == 0 for node in nodes
        ), plan
