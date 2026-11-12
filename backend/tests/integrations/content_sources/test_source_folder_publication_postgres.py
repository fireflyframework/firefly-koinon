# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Canonical mutation ordering and retained folder origin on real PostgreSQL."""

import asyncio
import hashlib
import json
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from psycopg.types.json import Json
from sqlalchemy.orm import Session
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_concurrency_postgres import wait_for_blocked_connection
from test_source_migration_postgres import ROOT, load, upgrade_sources
from test_source_migration_postgres import source_database as source_database
from test_sync_schema_postgres import job_and_run, policy, state, work_and_observation

pytestmark = pytest.mark.integration
TABLE = "koinon_content_folder_publications"


def prepare(connection):
    policy(connection)
    state(connection)
    job_and_run(connection, "first")
    connection.execute("UPDATE koinon_content_objects SET remote_kind='folder' WHERE id='origin'")
    work_and_observation(connection)
    connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=1 WHERE id='first'")


def folder(connection, identifier="managed"):
    connection.execute(
        """INSERT INTO lattice_catalog
        (id,tenant_id,workspace_id,project_id,parent_id,kind,name,description,status,
         metadata_json,created_by,updated_by,created_at,updated_at)
        VALUES(%s,'retained','workspace','project','folder','folder','Managed','','ready',
        '{}','issuer|alice','issuer|alice',now(),now())""",
        (identifier,),
    )


def publication(
    connection,
    *,
    identifier="publication",
    observation="observation",
    previous=None,
    folder_id="managed",
    audited=True,
    complete=True,
    **changes,
):
    name, parent, workspace, project, kind, revision = connection.execute(
        "SELECT name,parent_id,workspace_id,project_id,kind,mutation_revision "
        "FROM lattice_catalog WHERE id=%s",
        (folder_id,),
    ).fetchone()
    digest = hashlib.sha256(
        json.dumps(
            ["koinon.folder-fields.v1", name, parent, workspace, project, kind], ensure_ascii=False
        ).encode()
    ).hexdigest()
    values = dict(
        id=identifier,
        tenant_id="retained",
        mapping_id="mapping",
        object_id="origin",
        observation_id=observation,
        work_id="work",
        local_folder_id=folder_id,
        local_parent_id=parent,
        canonical_revision=revision,
        canonical_sha256=digest,
        previous_publication_id=previous,
    )
    values.update(changes)
    if audited:
        details = {
            key: values[key]
            for key in ("object_id", "observation_id", "work_id", "canonical_revision", "canonical_sha256")
        }
        details["publication_id"] = identifier
        connection.execute(
            "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
            "VALUES(%s,'retained','issuer|alice','source.folder.published',%s,%s,now())",
            (str(uuid4()), folder_id, Json(details)),
        )
    connection.execute(
        sql.SQL("INSERT INTO {} ({},created_at) VALUES ({},now())").format(
            sql.Identifier(TABLE),
            sql.SQL(",").join(map(sql.Identifier, values)),
            sql.SQL(",").join(sql.Placeholder() for _ in values),
        ),
        tuple(values.values()),
    )
    if complete:
        if previous is None:
            connection.execute(
                "INSERT INTO koinon_content_folder_bindings VALUES"
                "('retained','mapping','remote-file',%s,'root',%s,'[\"root\"]',1,now())",
                (folder_id, parent),
            )
        else:
            connection.execute(
                "UPDATE koinon_content_folder_bindings SET revision=revision+1,local_parent_id=%s "
                "WHERE local_folder_id=%s",
                (parent, folder_id),
            )
        connection.execute(
            "UPDATE koinon_content_objects SET published_local_revision=%s,published_sha256=%s,"
            "published_native_version_id=NULL WHERE id='origin'",
            (str(revision), digest),
        )
    return values


def observation_again(connection):
    connection.execute(
        "INSERT INTO koinon_content_sync_observations SELECT "
        "(jsonb_populate_record(NULL::koinon_content_sync_observations,"
        'to_jsonb(o)||\'{"id":"second","page_sequence":2}\'::jsonb)).* '
        "FROM koinon_content_sync_observations o WHERE id='observation'"
    )
    connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=2 WHERE id='first'")


async def test_canonical_revision_counts_noop_and_reverted_edits(source_sessions, source_database):
    _, uri = source_sessions
    _, _, engine = source_database
    assert "mutation_revision" in {row["name"] for row in sa.inspect(engine).get_columns("lattice_catalog")}
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            "SELECT mutation_revision FROM lattice_catalog WHERE id='folder'"
        ).fetchone() == (1,)
        for name, expected in (("changed", 2), ("folder", 3), ("folder", 4)):
            assert connection.execute(
                "UPDATE lattice_catalog SET name=%s WHERE id='folder' RETURNING mutation_revision",
                (name,),
            ).fetchone() == (expected,)
        connection.rollback()
        assert connection.execute(
            "SELECT name,mutation_revision FROM lattice_catalog WHERE id='folder'"
        ).fetchone() == ("folder", 1)


async def test_server_revision_rejects_assignment_and_orm_refreshes(source_sessions, source_database):
    from koinon.catalog.entities import CatalogEntry

    _, uri = source_sessions
    _, _, engine = source_database
    with psycopg.connect(uri) as connection:
        for value in (0, 2, -1, None):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(
                    "UPDATE lattice_catalog SET mutation_revision=%s WHERE id='folder'", (value,)
                )
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            connection.execute(
                "INSERT INTO lattice_catalog SELECT (jsonb_populate_record(NULL::lattice_catalog,"
                'to_jsonb(c)||\'{"id":"forged","mutation_revision":9}\'::jsonb)).* '
                "FROM lattice_catalog c WHERE id='folder'"
            )
    with Session(engine, expire_on_commit=False) as session:
        row = session.get(CatalogEntry, "folder")
        assert row.mutation_revision == 1
        row.description = "Internal update"
        session.flush()
        assert row.mutation_revision == 2
        session.rollback()


async def test_folder_publication_retains_exact_history_and_rollback(source_sessions, source_database):
    _, uri = source_sessions
    _, _, engine = source_database
    with psycopg.connect(uri) as connection:
        prepare(connection)
        folder(connection)
        first = publication(connection)
        connection.commit()
        connection.execute("UPDATE lattice_catalog SET name='Renamed' WHERE id='managed'")
        observation_again(connection)
        second = publication(connection, identifier="next", observation="second", previous="publication")
        connection.commit()
        assert (first["canonical_revision"], second["canonical_revision"]) == (1, 2)
        assert connection.execute(
            "SELECT id,previous_publication_id FROM koinon_content_folder_publications "
            "ORDER BY canonical_revision"
        ).fetchall() == [("publication", None), ("next", "publication")]
        connection.execute("UPDATE lattice_catalog SET name='Abandoned' WHERE id='managed'")
        connection.rollback()
        assert connection.execute(
            "SELECT name,mutation_revision FROM lattice_catalog WHERE id='managed'"
        ).fetchone() == ("Renamed", 2)
        connection.execute("UPDATE koinon_content_objects SET state='removed' WHERE id='origin'")
        connection.commit()
        assert connection.execute("SELECT count(*) FROM koinon_content_folder_publications").fetchone() == (
            2,
        )
    from koinon.integrations.content_sources.sync_entities import SourceFolderPublication

    actual = {row["name"]: row for row in sa.inspect(engine).get_columns(TABLE)}
    assert set(actual) == set(SourceFolderPublication.__table__.columns.keys())
    assert all(
        actual[col.name]["nullable"] == col.nullable for col in SourceFolderPublication.__table__.columns
    )


@pytest.mark.parametrize(
    "change",
    [
        {"audited": False},
        {"local_parent_id": "project"},
        {"canonical_revision": 2},
        {"tenant_id": "other"},
        {"work_id": "foreign"},
        {"observation_id": "foreign"},
        {"object_id": "foreign"},
        {"previous": "foreign"},
        {"canonical_sha256": "not-a-hash"},
        {"canonical_sha256": "e" * 64},
    ],
)
async def test_folder_origin_rejects_forged_typed_identity(source_sessions, change):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        folder(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            publication(connection, **change)
        assert connection.execute("SELECT count(*) FROM koinon_content_folder_publications").fetchone() == (
            0,
        )


async def test_initial_publication_cannot_adopt_retained_folder(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        folder(connection)
        connection.commit()
        with pytest.raises(psycopg.errors.CheckViolation, match="newly allocated"), connection.transaction():
            publication(connection)
        assert connection.execute("SELECT count(*) FROM koinon_content_folder_publications").fetchone() == (
            0,
        )


async def test_incomplete_publication_rolls_back_folder_ledger_audit_and_baseline(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        connection.commit()
        folder(connection)
        publication(connection, complete=False)
        with pytest.raises(psycopg.errors.CheckViolation, match="baseline must commit"):
            connection.commit()
        assert connection.execute("SELECT count(*) FROM lattice_catalog WHERE id='managed'").fetchone() == (
            0,
        )
        assert connection.execute("SELECT count(*) FROM koinon_content_folder_publications").fetchone() == (
            0,
        )
        assert connection.execute(
            "SELECT count(*) FROM lattice_audit WHERE action='source.folder.published'"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT published_local_revision FROM koinon_content_objects WHERE id='origin'"
        ).fetchone() == (None,)


async def test_publication_grants_and_guards_preserve_history(source_sessions, source_database):
    _, uri = source_sessions
    target, role, _ = source_database
    with psycopg.connect(uri) as connection:
        prepare(connection)
        folder(connection)
        publication(connection)
        load("deploy/provision_roles.py").grant_table(connection, TABLE, role)
        connection.commit()
        for statement in (
            "UPDATE koinon_content_folder_publications SET canonical_revision=9",
            "DELETE FROM koinon_content_folder_publications",
            "TRUNCATE koinon_content_folder_publications",
        ):
            with pytest.raises(psycopg.errors.CheckViolation, match="immutable"), connection.transaction():
                connection.execute(statement)
    runtime_uri = target.set(drivername="postgresql", username=role, password=None).render_as_string(
        hide_password=False
    )
    with psycopg.connect(runtime_uri) as runtime:
        assert runtime.execute("SELECT count(*) FROM koinon_content_folder_publications").fetchone() == (1,)
        for statement in (
            "UPDATE koinon_content_folder_publications SET canonical_revision=9",
            "DELETE FROM koinon_content_folder_publications",
            "TRUNCATE koinon_content_folder_publications",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime.transaction():
                runtime.execute(statement)
        with pytest.raises(psycopg.errors.CheckViolation), runtime.transaction():
            runtime.execute("UPDATE lattice_catalog SET mutation_revision=99 WHERE id='managed'")


def test_upgrade_retains_existing_catalog_and_adds_no_invented_origins(source_database):
    _, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0048_source_recovery")
        connection.commit()
        connection.exec_driver_sql(
            "INSERT INTO lattice_catalog(id,tenant_id,kind,name,description,status,metadata_json,"
            "created_by,updated_by,created_at,updated_at) VALUES('old','retained','workspace',"
            "'Retained','','ready','{}','owner','owner',now(),now())"
        )
        connection.commit()
        before = connection.exec_driver_sql("SELECT to_jsonb(c) FROM lattice_catalog c").scalar_one()
    upgrade_sources(engine)
    with engine.connect() as connection:
        assert (
            connection.exec_driver_sql(
                "SELECT to_jsonb(c)-'mutation_revision' FROM lattice_catalog c"
            ).scalar_one()
            == before
        )
        assert connection.exec_driver_sql("SELECT mutation_revision FROM lattice_catalog").scalar_one() == 1
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM koinon_content_folder_publications").scalar_one()
            == 0
        )


@pytest.mark.parametrize("failure", ["index", "expansion"])
def test_interrupted_folder_migration_retries_without_partial_schema(source_database, failure):
    _, _, engine = source_database
    migrate = load("deploy/migrate.py")
    versions = ROOT / "deploy/migrations/native_versions"
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("native", versions, connection), "koinon_0048_source_recovery")
        connection.commit()
    needle = (
        "ix_content_folder_audit ON"
        if failure == "index"
        else "CREATE TABLE koinon_content_folder_publications"
    )

    def interrupt(connection, cursor, statement, parameters, context, executemany):
        if needle in statement:
            raise RuntimeError("owned folder migration interruption")

    with engine.connect() as connection:
        sa.event.listen(connection, "before_cursor_execute", interrupt)
        try:
            with pytest.raises(RuntimeError, match="owned folder migration interruption"):
                command.upgrade(
                    migrate.history_config("native", versions, connection), "koinon_0049_source_folders"
                )
        finally:
            sa.event.remove(connection, "before_cursor_execute", interrupt)
            connection.rollback()
        assert (
            connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar_one()
            == "koinon_0048_source_recovery"
        )
        assert (
            connection.exec_driver_sql(
                "SELECT to_regclass('koinon_content_folder_publications')"
            ).scalar_one()
            is None
        )
        assert "mutation_revision" not in {
            row["name"] for row in sa.inspect(connection).get_columns("lattice_catalog")
        }
        assert connection.exec_driver_sql(
            "SELECT indisvalid FROM pg_index WHERE indexrelid='uq_content_observation_publication'::regclass"
        ).scalar_one()
    with engine.connect() as connection:
        command.upgrade(migrate.history_config("native", versions, connection), "koinon_0049_source_folders")
        connection.commit()
        assert (
            connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar_one()
            == "koinon_0049_source_folders"
        )
        assert (
            connection.exec_driver_sql("SELECT count(*) FROM koinon_content_folder_publications").scalar_one()
            == 0
        )


async def test_opposing_local_edit_rejects_stale_folder_publication(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        folder(connection)
        publication(connection)
        connection.commit()
        observation_again(connection)
        connection.execute("UPDATE lattice_catalog SET name='Planned' WHERE id='managed'")
        connection.commit()
        expected = hashlib.sha256(
            json.dumps(
                ["koinon.folder-fields.v1", "Planned", "folder", "workspace", "project", "folder"]
            ).encode()
        ).hexdigest()
        connection.execute(
            "INSERT INTO lattice_audit VALUES('second-audit','retained','issuer|alice',"
            "'source.folder.published','managed',%s,now())",
            (
                Json(
                    dict(
                        publication_id="next",
                        object_id="origin",
                        observation_id="second",
                        work_id="work",
                        canonical_revision=2,
                        canonical_sha256=expected,
                    )
                ),
            ),
        )
        connection.commit()
    first = await psycopg.AsyncConnection.connect(uri)
    second = await psycopg.AsyncConnection.connect(uri, application_name="stale-folder-publication")
    task = None
    try:
        await first.execute("UPDATE lattice_catalog SET name='Local edit' WHERE id='managed'")
        task = asyncio.create_task(
            second.execute(
                "INSERT INTO koinon_content_folder_publications VALUES"
                "('next','retained','mapping','origin','second','work','managed','folder',2,%s,'publication',now())",
                (expected,),
            )
        )
        await wait_for_blocked_connection(uri, "stale-folder-publication")
        await first.commit()
        with pytest.raises(psycopg.errors.CheckViolation, match="identity mismatch"):
            await task
        await second.rollback()
        assert await (
            await second.execute("SELECT name,mutation_revision FROM lattice_catalog WHERE id='managed'")
        ).fetchone() == ("Local edit", 3)
        assert await (
            await second.execute("SELECT count(*) FROM koinon_content_folder_publications")
        ).fetchone() == (1,)
    finally:
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await first.close()
        await second.close()


def test_retry_rebuilds_invalid_concurrent_index(source_database):
    target, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0048_source_recovery")
        connection.commit()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(
            "INSERT INTO lattice_audit VALUES('index-seed','retained','owner','test',NULL,'{}',now())"
        )
        with pytest.raises(psycopg.errors.DivisionByZero):
            connection.execute(
                "CREATE INDEX CONCURRENTLY ix_content_folder_audit ON lattice_audit "
                "((length(subject)/(length(subject)-length(subject))))"
            )
        assert connection.execute(
            "SELECT indisvalid FROM pg_index WHERE indexrelid='ix_content_folder_audit'::regclass"
        ).fetchone() == (False,)
    upgrade_sources(engine)
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            "SELECT indisvalid FROM pg_index WHERE indexrelid='ix_content_folder_audit'::regclass"
        ).fetchone() == (True,)
        assert (
            "WHERE ((action)::text = 'source.folder.published'::text)"
            in connection.execute("SELECT pg_get_indexdef('ix_content_folder_audit'::regclass)").fetchone()[0]
        )


async def test_folder_lookup_uses_index_with_ten_thousand_origins(source_sessions, record_property):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        prepare(connection)
        # All generated rows pass the same guards as ordinary initial publication.
        connection.execute("""INSERT INTO lattice_catalog
            (id,tenant_id,workspace_id,project_id,parent_id,kind,name,description,status,
             metadata_json,created_by,updated_by,created_at,updated_at)
            SELECT 'managed-'||n,'retained','workspace','project','folder','folder','Folder '||n,
            '','ready','{}','issuer|alice','issuer|alice',now(),now() FROM generate_series(1,10000) n""")
        connection.execute("""INSERT INTO koinon_content_objects
            SELECT (jsonb_populate_record(NULL::koinon_content_objects,to_jsonb(o)||
                jsonb_build_object('id','object-'||n,'item_id','remote-'||n,
                  'published_local_revision','1','published_sha256',
                  encode(sha256(convert_to(jsonb_build_array('koinon.folder-fields.v1',
                    'Folder '||n,'folder','workspace','project','folder')::text,'UTF8')),'hex')))).*
            FROM koinon_content_objects o CROSS JOIN generate_series(1,10000) n WHERE o.id='origin'""")
        connection.execute("""INSERT INTO koinon_content_sync_work
            SELECT (jsonb_populate_record(NULL::koinon_content_sync_work,to_jsonb(w)||
            jsonb_build_object('id','work-'||n,'object_id','object-'||n))).*
            FROM koinon_content_sync_work w CROSS JOIN generate_series(1,10000) n WHERE w.id='work'""")
        connection.execute("""INSERT INTO koinon_content_sync_observations
            SELECT (jsonb_populate_record(NULL::koinon_content_sync_observations,to_jsonb(o)||
            jsonb_build_object('id','observation-'||n,'object_id','object-'||n,'work_id','work-'||n,
            'page_sequence',2,'item_sequence',n))).* FROM koinon_content_sync_observations o
            CROSS JOIN generate_series(1,10000) n WHERE o.id='observation'""")
        connection.execute("UPDATE koinon_content_sync_runs SET page_sequence=2 WHERE id='first'")
        connection.execute("""INSERT INTO koinon_content_folder_bindings
            SELECT 'retained','mapping','remote-'||n,'managed-'||n,'root','folder','["root"]',1,now()
            FROM generate_series(1,10000) n""")
        connection.execute("""INSERT INTO lattice_audit
            SELECT 'audit-'||n,'retained','issuer|alice','source.folder.published','managed-'||n,
            jsonb_build_object('publication_id','publication-'||n,'object_id','object-'||n,
              'observation_id','observation-'||n,'work_id','work-'||n,'canonical_revision',1,
              'canonical_sha256',o.published_sha256),now()
            FROM generate_series(1,10000) n JOIN koinon_content_objects o ON o.id='object-'||n""")
        connection.execute("""INSERT INTO koinon_content_folder_publications
            SELECT 'publication-'||n,'retained','mapping','object-'||n,'observation-'||n,'work-'||n,
              'managed-'||n,'folder',1,o.published_sha256,NULL,now()
            FROM generate_series(1,10000) n JOIN koinon_content_objects o ON o.id='object-'||n""")
        connection.commit()
        connection.execute("ANALYZE koinon_content_folder_publications")
        plan = connection.execute("""EXPLAIN (ANALYZE, FORMAT JSON) SELECT id
            FROM koinon_content_folder_publications WHERE tenant_id='retained'
            AND local_folder_id='managed-9800' ORDER BY canonical_revision DESC LIMIT 1""").fetchone()[0][0][
            "Plan"
        ]
        record_property("folder_lookup_plan", json.dumps(plan))
        assert plan["Actual Rows"] == 1
        assert any(
            node.get("Index Name") == "ix_content_folder_publication_history"
            for node in [plan, *plan.get("Plans", [])]
        )


@pytest.mark.parametrize("mutation", ["counter", "digest", "new_folder", "atomic_commit", "immutable"])
async def test_folder_behavior_detects_removed_database_guard(
    source_sessions, source_database, mutation, record_property
):
    """Only mutate the isolated synthetic database, never shared production files."""
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0].startswith("source_schema_")
        if mutation in {"digest", "new_folder"}:
            definition = connection.execute(
                "SELECT pg_get_functiondef('koinon_folder_publication_guard()'::regprocedure)"
            ).fetchone()[0]
            before, after = (
                (
                    "OR NEW.canonical_sha256 IS DISTINCT FROM encode",
                    "OR false AND NEW.canonical_sha256 IS DISTINCT FROM encode",
                )
                if mutation == "digest"
                else ("OR NOT inserted_here", "OR false")
            )
            assert before in definition
            connection.execute(definition.replace(before, after, 1))
        else:
            table, trigger = {
                "counter": ("lattice_catalog", "guard_catalog_revision"),
                "atomic_commit": (TABLE, "complete_folder_publication"),
                "immutable": (TABLE, "guard_folder_publication"),
            }[mutation]
            connection.execute(
                sql.SQL("DROP TRIGGER {} ON {}").format(sql.Identifier(trigger), sql.Identifier(table))
            )
    if mutation == "counter":
        with pytest.raises(AssertionError):
            await test_canonical_revision_counts_noop_and_reverted_edits(source_sessions, source_database)
    else:
        with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
            if mutation == "digest":
                await test_folder_origin_rejects_forged_typed_identity(
                    source_sessions, {"canonical_sha256": "e" * 64}
                )
            elif mutation == "new_folder":
                await test_initial_publication_cannot_adopt_retained_folder(source_sessions)
            elif mutation == "atomic_commit":
                await test_incomplete_publication_rolls_back_folder_ledger_audit_and_baseline(source_sessions)
            else:
                await test_publication_grants_and_guards_preserve_history(source_sessions, source_database)
    record_property("detected_mutation", mutation)
