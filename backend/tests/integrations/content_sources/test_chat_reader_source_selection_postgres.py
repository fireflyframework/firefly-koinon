# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Persist bounded, immutable reader choices on the actual primary database."""

import json

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from psycopg.types.json import Json
from sqlalchemy.orm import Session
from test_source_migration_postgres import ROOT, load, upgrade_sources
from test_source_migration_postgres import source_database as source_database

from koinon.catalog.entities import Tenant as Tenant

pytestmark = pytest.mark.integration
LOCAL = {"version": 1, "mode": "local_only", "revision": None, "connections": []}
CHOICE = {"provider": "google_drive", "connection_id": "personal"}
EXPLICIT = {"version": 1, "mode": "explicit", "revision": None, "connections": [CHOICE]}
SAVED = {"version": 1, "mode": "saved", "revision": 7, "connections": [CHOICE]}


def seed_conversation(connection):
    connection.execute("""INSERT INTO koinon_providers
        (id,tenant_id,name,kind,base_url,model_ids,enabled,validated_revision,checks,revision,
         created_at,updated_at)
        VALUES('provider','retained','Local','openai','https://model.invalid','[]',true,1,'[]',1,
               now(),now())""")
    connection.execute("""INSERT INTO koinon_agents
        (id,tenant_id,provider_id,name,description,model_id,tools,scope,instructions,enabled,
         revision,created_at,updated_at)
        VALUES('agent','retained','provider','Assistant','','model','[]','{}','',true,1,now(),now())""")
    connection.execute("""INSERT INTO koinon_chat_threads
        (id,tenant_id,subject,title,scope,created_at,updated_at)
        VALUES('thread','retained','issuer|reader','Retained conversation','{}',now(),now())""")
    connection.execute("""INSERT INTO koinon_chat_messages
        (id,thread_id,role,text,status,presentation,citations,artifacts,created_at)
        VALUES('question','thread','user','Question','completed','{}','[]','[]',now()),
              ('answer','thread','assistant','','pending','{}','[]','[]',now())""")


def insert_run(connection, selection, identifier="run"):
    connection.execute(
        """INSERT INTO koinon_chat_runs
        (id,tenant_id,thread_id,message_id,user_message_id,agent_id,agent_revision,provider_revision,
         scope,client_request_id,payload_hash,status,available_at,attempts,sequence,created_at,
         updated_at,reader_source_selection)
        VALUES(%s,'retained','thread','answer','question','agent',1,1,'{}',%s,'digest','queued',
               now(),0,0,now(),now(),%s)""",
        (identifier, identifier, selection),
    )


@pytest.fixture
def run_database(source_database):
    target, role, engine = source_database
    upgrade_sources(engine)
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        seed_conversation(connection)
    return uri, role, engine


def test_queued_source_selection_expands_without_invented_defaults(source_database):
    _, _, engine = source_database
    upgrade_sources(engine)
    with engine.connect() as connection:
        columns = {row["name"]: row for row in sa.inspect(connection).get_columns("koinon_chat_runs")}
        assert "reader_source_selection" in columns, "queued source intent has no durable storage"
        assert columns["reader_source_selection"]["nullable"]
        assert columns["reader_source_selection"]["default"] is None


@pytest.mark.parametrize(
    "selection",
    [
        None,
        LOCAL,
        EXPLICIT,
        SAVED,
        {"version": 1, "mode": "saved", "revision": 0, "connections": []},
        {
            **EXPLICIT,
            "connections": [
                {"provider": "sharepoint", "connection_id": "s" * 64, "external_tenant": "t" * 1024},
                {"provider": "onedrive", "connection_id": "o", "external_tenant": None},
                CHOICE,
            ],
        },
        {**EXPLICIT, "connections": [{**CHOICE, "external_tenant": str(i)} for i in range(100)]},
    ],
    ids=["legacy-null", "local", "explicit", "saved", "saved-empty", "providers-and-id-bounds", "hundred"],
)
def test_persists_exact_selection_without_resolving_defaults(run_database, selection):
    uri, _, _ = run_database
    with psycopg.connect(uri) as connection:
        insert_run(connection, None if selection is None else Json(selection))
        connection.execute("UPDATE koinon_chat_runs SET status='running',attempts=1 WHERE id='run'")
        assert connection.execute(
            "SELECT reader_source_selection,status,attempts FROM koinon_chat_runs WHERE id='run'"
        ).fetchone() == (selection, "running", 1)


INVALID_SELECTIONS = [
    pytest.param(None, id="json-null"),
    pytest.param([], id="top-array"),
    pytest.param(1, id="top-number"),
    *[
        pytest.param({key: value for key, value in LOCAL.items() if key != missing}, id="missing-" + missing)
        for missing in LOCAL
    ],
    pytest.param({**LOCAL, "token": "secret"}, id="unknown-key"),
    *[
        pytest.param({**LOCAL, "version": version}, id="version-" + str(version))
        for version in (True, "1", 1.0, 0, 2)
    ],
    *[pytest.param({**LOCAL, "mode": mode}, id="mode-" + str(mode)) for mode in (None, True, "default")],
    *[
        pytest.param({**SAVED, "revision": revision}, id="revision-" + str(revision))
        for revision in (None, True, False, -1, 1.5, 1.0, "7")
    ],
    pytest.param({**EXPLICIT, "revision": 1}, id="explicit-revision"),
    pytest.param({**LOCAL, "revision": 0}, id="local-revision"),
    pytest.param({**EXPLICIT, "connections": []}, id="explicit-empty"),
    pytest.param({**LOCAL, "connections": [CHOICE]}, id="local-connections"),
    pytest.param({**EXPLICIT, "connections": {}}, id="connection-object"),
    pytest.param({**EXPLICIT, "connections": [None]}, id="connection-null"),
    pytest.param(
        {**EXPLICIT, "connections": [CHOICE, {**CHOICE, "external_tenant": None}]}, id="duplicate-null-tenant"
    ),
    pytest.param(
        {**EXPLICIT, "connections": [{**CHOICE, "external_tenant": str(i)} for i in range(101)]},
        id="too-many",
    ),
    *[
        pytest.param(
            {**EXPLICIT, "connections": [{**CHOICE, "provider": provider}]}, id="provider-" + str(provider)
        )
        for provider in ("grok", None, 1)
    ],
    *[
        pytest.param(
            {**EXPLICIT, "connections": [{**CHOICE, "connection_id": identifier}]}, id="id-" + str(identifier)
        )
        for identifier in (None, True, 1, "", "x" * 65)
    ],
    *[
        pytest.param(
            {**EXPLICIT, "connections": [{**CHOICE, "external_tenant": tenant}]}, id="tenant-" + str(tenant)
        )
        for tenant in (True, 1, "", "x" * 1025)
    ],
    pytest.param({**EXPLICIT, "connections": [{"provider": "google_drive"}]}, id="missing-id"),
    pytest.param({**EXPLICIT, "connections": [{"connection_id": "c"}]}, id="missing-provider"),
    pytest.param({**EXPLICIT, "connections": [{**CHOICE, "token": "secret"}]}, id="nested-unknown"),
    pytest.param(
        {
            **EXPLICIT,
            "connections": [
                {**CHOICE, "external_tenant": "same"},
                {**CHOICE, "external_tenant": "same", "connection_id": "other"},
            ],
        },
        id="duplicate-tenant-different-id",
    ),
]


@pytest.mark.parametrize("selection", INVALID_SELECTIONS)
def test_rejects_malformed_or_ambiguous_selection(run_database, selection):
    uri, _, _ = run_database
    with psycopg.connect(uri) as connection:
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            insert_run(connection, Json(selection))
        assert connection.execute("SELECT count(*) FROM koinon_chat_runs").fetchone() == (0,)


@pytest.mark.parametrize(
    "raw",
    [
        '{"version":1,"mode":"local_only","revision":null,"connections":[],"mode":"local_only"}',
        '{"version":1,"mode":"explicit","revision":null,"connections":'
        '[{"provider":"google_drive","connection_id":"a","connection_id":"b"}]}',
    ],
)
def test_rejects_duplicate_json_keys(run_database, raw):
    uri, _, _ = run_database
    with psycopg.connect(uri) as connection, pytest.raises(psycopg.errors.CheckViolation):
        insert_run(connection, raw)


def test_enforces_serialized_utf8_size_at_exact_boundary(run_database):
    uri, _, _ = run_database
    # Unicode keeps every string within its character bound while exhausting bytes.
    selection = {
        **EXPLICIT,
        "connections": [{**CHOICE, "external_tenant": str(i) + "界" * 900} for i in range(48)],
    }
    raw = json.dumps(selection, ensure_ascii=False, separators=(",", ":"))
    # Remove complete characters until this valid selection fits, then pad JSON whitespace.
    selection["connections"].pop()
    fitting = json.dumps(selection, ensure_ascii=False, separators=(",", ":"))
    assert len(fitting.encode()) < 131072 < len(raw.encode())
    exact = fitting + " " * (131072 - len(fitting.encode()))
    with psycopg.connect(uri) as connection:
        insert_run(connection, exact, "exact")
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            insert_run(connection, exact + " ", "too-large")
        assert connection.execute(
            "SELECT reader_source_selection FROM koinon_chat_runs WHERE id='exact'"
        ).fetchone() == (selection,)


@pytest.mark.parametrize(
    "before,after",
    [
        (None, None),
        (None, LOCAL),
        (SAVED, None),
        (SAVED, SAVED),
        (SAVED, EXPLICIT),
    ],
)
def test_rejects_every_retained_selection_assignment(run_database, before, after):
    uri, _, _ = run_database
    with psycopg.connect(uri) as connection:
        insert_run(connection, None if before is None else Json(before))
        with pytest.raises(psycopg.errors.CheckViolation, match="immutable"), connection.transaction():
            connection.execute(
                "UPDATE koinon_chat_runs SET reader_source_selection=%s WHERE id='run'",
                (None if after is None else Json(after),),
            )
        assert connection.execute("SELECT reader_source_selection FROM koinon_chat_runs").fetchone() == (
            before,
        )


def test_orm_none_stores_sql_null_and_can_update_run_status(run_database):
    from koinon.assistants.entities import ChatRun

    _, _, engine = run_database
    with Session(engine) as session:
        session.add(
            ChatRun(
                id="orm",
                tenant_id="retained",
                thread_id="thread",
                message_id="answer",
                user_message_id="question",
                agent_id="agent",
                agent_revision=1,
                provider_revision=1,
                client_request_id="orm",
                payload_hash="digest",
                reader_source_selection=None,
            )
        )
        session.commit()
        run = session.get(ChatRun, "orm")
        assert run is not None
        run.status = "running"
        session.commit()
        assert session.execute(
            sa.text("SELECT reader_source_selection IS NULL,status FROM koinon_chat_runs WHERE id='orm'")
        ).one() == (True, "running")


def test_prior_head_upgrade_preserves_existing_run_bytes(source_database):
    target, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0049_source_folders")
        connection.commit()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        seed_conversation(connection)
        connection.execute("""INSERT INTO koinon_chat_runs
            (id,tenant_id,thread_id,message_id,user_message_id,agent_id,agent_revision,provider_revision,
             scope,client_request_id,payload_hash,status,available_at,attempts,sequence,created_at,updated_at)
            VALUES('retained-run','retained','thread','answer','question','agent',1,1,'{"scope":"original"}',
                   'original','original-digest','queued',now(),2,3,now(),now())""")
        before = connection.execute("SELECT to_jsonb(r) FROM koinon_chat_runs r").fetchone()[0]
    upgrade_sources(engine)
    with psycopg.connect(uri) as connection:
        after = connection.execute("SELECT to_jsonb(r) FROM koinon_chat_runs r").fetchone()[0]
        assert after.pop("reader_source_selection") is None
        assert after == before


@pytest.mark.parametrize("needle", ["CREATE FUNCTION", "CREATE TRIGGER"])
def test_interrupted_selection_upgrade_rolls_back_and_retries(source_database, needle):
    _, _, engine = source_database
    migrate = load("deploy/migrate.py")
    versions = ROOT / "deploy/migrations/native_versions"
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("native", versions, connection), "koinon_0049_source_folders")
        connection.commit()

        def interrupt(connection, cursor, statement, parameters, context, executemany):
            if needle in statement:
                raise RuntimeError("owned selection migration interruption")

        sa.event.listen(connection, "before_cursor_execute", interrupt)
        try:
            with pytest.raises(RuntimeError, match="owned selection migration interruption"):
                command.upgrade(migrate.history_config("native", versions, connection), "head")
        finally:
            sa.event.remove(connection, "before_cursor_execute", interrupt)
            connection.rollback()
        assert (
            connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar_one()
            == "koinon_0049_source_folders"
        )
        assert "reader_source_selection" not in {
            column["name"] for column in sa.inspect(connection).get_columns("koinon_chat_runs")
        }
        assert (
            connection.exec_driver_sql(
                "SELECT to_regprocedure('public.koinon_chat_reader_selection_guard()')"
            ).scalar_one()
            is None
        )
    upgrade_sources(engine)
    with engine.connect() as connection:
        assert "reader_source_selection" in {
            column["name"] for column in sa.inspect(connection).get_columns("koinon_chat_runs")
        }


def test_runtime_role_cannot_rewrite_or_disable_selection_guards(run_database):
    uri, role, _ = run_database
    with psycopg.connect(uri) as owner:
        load("deploy/provision_roles.py").grant_table(owner, "koinon_chat_runs", role)
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
    with psycopg.connect(uri, user=role) as runtime:
        insert_run(runtime, Json(SAVED))
        runtime.execute("UPDATE koinon_chat_runs SET status='running' WHERE id='run'")
        with pytest.raises(psycopg.errors.CheckViolation, match="immutable"), runtime.transaction():
            runtime.execute("UPDATE koinon_chat_runs SET reader_source_selection=reader_source_selection")
        with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime.transaction():
            runtime.execute("ALTER TABLE koinon_chat_runs DISABLE TRIGGER koinon_chat_reader_selection_guard")
        assert runtime.execute(
            "SELECT has_function_privilege(current_user,"
            "'public.koinon_chat_reader_selection_guard()','EXECUTE')"
        ).fetchone() == (False,)
        assert runtime.execute("SELECT reader_source_selection,status FROM koinon_chat_runs").fetchone() == (
            SAVED,
            "running",
        )


def test_selection_lookup_uses_existing_run_key_with_ten_thousand_runs(run_database):
    uri, _, _ = run_database
    with psycopg.connect(uri) as connection:
        insert_run(connection, Json(SAVED))
        connection.execute("""INSERT INTO koinon_chat_runs
            (id,tenant_id,thread_id,message_id,user_message_id,agent_id,agent_revision,provider_revision,
             scope,client_request_id,payload_hash,status,available_at,attempts,sequence,created_at,
             updated_at,reader_source_selection)
            SELECT 'run-'||n,tenant_id,thread_id,message_id,user_message_id,agent_id,agent_revision,
                   provider_revision,scope,'request-'||n,payload_hash,status,available_at,attempts,sequence,
                   created_at,updated_at,reader_source_selection
            FROM koinon_chat_runs CROSS JOIN generate_series(1,10000) AS n WHERE id='run'""")
        connection.execute("ANALYZE koinon_chat_runs")
        plan = connection.execute(
            "EXPLAIN (ANALYZE,FORMAT JSON) SELECT reader_source_selection "
            "FROM koinon_chat_runs WHERE id='run-5000'"
        ).fetchone()[0][0]["Plan"]
        assert plan["Node Type"] == "Index Scan"
        assert plan["Index Name"] == "pk_koinon_chat_runs"
        assert plan["Actual Rows"] == 1
