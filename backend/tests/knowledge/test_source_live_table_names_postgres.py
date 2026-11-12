# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Live table names remain unique while original historical identities survive."""

import importlib.util
from pathlib import Path
from typing import cast
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from alembic.config import Config
from psycopg import sql
from sqlalchemy import Table as SQLTable
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location(
    "live_names_fixture",
    Path(__file__).parents[1] / "integrations/content_sources/test_source_migration_postgres.py",
)
assert _spec is not None and _spec.loader is not None
_fixture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixture)
source_database = _fixture.source_database


def configuration(connection, product):
    config = _fixture.load("deploy/migrate.py").history_config(
        "structured", ROOT / "packages/structured/migrations/versions", connection
    )
    if not product:
        config.set_main_option("version_locations", str(ROOT / "packages/structured/migrations/versions"))
        config.attributes["version_table"] = "alembic_version"
    return config


def upgrade(engine, revision="head", *, product=True):
    with engine.connect() as connection:
        command.upgrade(configuration(connection, product), revision)
        connection.commit()


def dataset(connection):
    identifier, workspace = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO flyquery_workspaces(id,tenant_id,slug,name) VALUES(%s,'tenant',%s,'Workspace')",
        (workspace, str(workspace)),
    )
    connection.execute(
        "INSERT INTO flyquery_datasets(id,tenant_id,workspace_id,name) VALUES(%s,'tenant',%s,'Dataset')",
        (identifier, workspace),
    )
    return identifier, workspace


def table(connection, scope, name="orders", *, active=True):
    identifier = uuid4()
    connection.execute(
        "INSERT INTO flyquery_tables(id,tenant_id,workspace_id,dataset_id,name,qualified_name,is_active) "
        "VALUES(%s,'tenant',%s,%s,%s,%s,%s)",
        (identifier, scope[1], scope[0], name, "dataset." + name, active),
    )
    return identifier


@pytest.mark.parametrize("product", [False, True])
def test_same_name_replacement_retains_exact_history_and_live_uniqueness(source_database, product):
    target, _, engine = source_database
    upgrade(engine, product=product)
    with psycopg.connect(
        target.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        scope = dataset(connection)
        old = table(connection, scope)
        replacement = table(connection, scope, active=False)
        connection.execute("UPDATE flyquery_tables SET is_active=false,archived_at=now() WHERE id=%s", (old,))
        connection.execute("UPDATE flyquery_tables SET is_active=true WHERE id=%s", (replacement,))
        assert connection.execute(
            "SELECT name,qualified_name,is_active,archived_at IS NOT NULL FROM flyquery_tables WHERE id=%s",
            (old,),
        ).fetchone() == ("orders", "dataset.orders", False, True)
        assert connection.execute(
            "SELECT id FROM flyquery_tables WHERE dataset_id=%s AND name='orders' AND is_active", (scope[0],)
        ).fetchone() == (replacement,)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            table(connection, scope)


def test_name_swap_is_atomic_and_failed_publication_restores_live_names(source_database):
    target, _, engine = source_database
    upgrade(engine)
    with psycopg.connect(
        target.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        scope = dataset(connection)
        first, second = table(connection, scope, "first"), table(connection, scope, "second")
        connection.commit()
        for abort in (True, False):
            with connection.transaction() as transaction:
                connection.execute(
                    "UPDATE flyquery_tables SET is_active=false WHERE dataset_id=%s", (scope[0],)
                )
                connection.execute(
                    "UPDATE flyquery_tables SET name=CASE WHEN id=%s THEN 'second' ELSE 'first' END, "
                    "qualified_name=CASE WHEN id=%s THEN 'dataset.second' ELSE 'dataset.first' END "
                    "WHERE dataset_id=%s",
                    (first, first, scope[0]),
                )
                connection.execute(
                    "UPDATE flyquery_tables SET is_active=true WHERE dataset_id=%s", (scope[0],)
                )
                if abort:
                    raise psycopg.Rollback(transaction)
            assert connection.execute(
                "SELECT name,qualified_name,is_active FROM flyquery_tables WHERE id=%s", (first,)
            ).fetchone() == (
                ("first", "dataset.first", True) if abort else ("second", "dataset.second", True)
            )
            assert connection.execute(
                "SELECT name,is_active FROM flyquery_tables WHERE id=%s", (second,)
            ).fetchone() == (("second", True) if abort else ("first", True))
            connection.commit()


def test_concurrent_activation_loser_rolls_back_without_changing_history(source_database):
    target, _, engine = source_database
    upgrade(engine)
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as setup:
        scope = dataset(setup)
        first, second = table(setup, scope, active=False), table(setup, scope, active=False)
    with psycopg.connect(uri) as winner, psycopg.connect(uri) as loser:
        winner.execute("UPDATE flyquery_tables SET is_active=true WHERE id=%s", (first,))
        with pytest.raises(psycopg.errors.LockNotAvailable), loser.transaction():
            loser.execute("SET LOCAL lock_timeout='100ms'")
            loser.execute("UPDATE flyquery_tables SET is_active=true WHERE id=%s", (second,))
        winner.commit()
        with pytest.raises(psycopg.errors.UniqueViolation), loser.transaction():
            loser.execute("UPDATE flyquery_tables SET is_active=true WHERE id=%s", (second,))
        assert loser.execute(
            "SELECT name,qualified_name,is_active,archived_at FROM flyquery_tables WHERE id=%s", (second,)
        ).fetchone() == ("orders", "dataset.orders", False, None)
        assert loser.execute(
            "SELECT id FROM flyquery_tables WHERE dataset_id=%s AND is_active", (scope[0],)
        ).fetchall() == [(first,)]


@pytest.mark.parametrize("product", [False, True])
@pytest.mark.parametrize("interruption", ["CREATE UNIQUE INDEX", "DROP CONSTRAINT"])
def test_interrupted_upgrade_rolls_back_and_retry_preserves_all_rows(source_database, product, interruption):
    target, _, engine = source_database
    previous = "0025_source_publication_baseline" if product else "0015_versioned_embedding_sets"
    upgrade(engine, previous, product=product)
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        scope = dataset(connection)
        table(connection, scope)
        historical = table(connection, scope, "historical", active=False)
        connection.execute("UPDATE flyquery_tables SET archived_at=now() WHERE id=%s", (historical,))
        before = connection.execute("SELECT to_jsonb(t) FROM flyquery_tables t ORDER BY id").fetchall()

    def interrupt(connection, cursor, statement, parameters, context, executemany):
        if interruption in statement and "uq_tables_dataset" in statement:
            raise RuntimeError("owned live-name migration interruption")

    with engine.connect() as connection:
        event.listen(connection, "after_cursor_execute", interrupt)
        try:
            with pytest.raises(RuntimeError, match="owned live-name migration interruption"):
                command.upgrade(configuration(connection, product), "head")
        finally:
            event.remove(connection, "after_cursor_execute", interrupt)
            connection.rollback()
    with psycopg.connect(uri) as connection:
        version_table = "koinon_structured_version" if product else "alembic_version"
        assert connection.execute(
            sql.SQL("SELECT version_num FROM {}").format(sql.Identifier(version_table))
        ).fetchall() == [(previous,)]
        assert (
            connection.execute("SELECT to_jsonb(t) FROM flyquery_tables t ORDER BY id").fetchall() == before
        )
        assert connection.execute("SELECT to_regclass('uq_tables_dataset_live_name')").fetchone() == (None,)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            table(connection, scope, active=False)
    upgrade(engine, product=product)
    upgrade(engine, product=product)
    with psycopg.connect(uri) as connection:
        assert (
            connection.execute("SELECT to_jsonb(t) FROM flyquery_tables t ORDER BY id").fetchall() == before
        )
        table(connection, scope, active=False)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            table(connection, scope)
    with engine.connect() as connection:
        with pytest.raises(RuntimeError, match="forward migration"):
            command.downgrade(configuration(connection, product), previous)
        connection.rollback()


def test_live_lookup_uses_partial_index_and_history_lookup_uses_primary_key(source_database):
    target, _, engine = source_database
    upgrade(engine)
    with psycopg.connect(
        target.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        scope = dataset(connection)
        connection.execute(
            "INSERT INTO flyquery_tables(tenant_id,workspace_id,dataset_id,name,qualified_name,is_active) "
            "SELECT 'tenant',%s,%s,'table-'||n,'dataset.table-'||n,n %% 2 = 0 "
            "FROM generate_series(1,10000) AS n",
            (scope[1], scope[0]),
        )
        connection.execute("ANALYZE flyquery_tables")
        live_row = connection.execute(
            "EXPLAIN (ANALYZE, FORMAT JSON) SELECT id FROM flyquery_tables "
            "WHERE dataset_id=%s AND name='table-9800' AND is_active",
            (scope[0],),
        ).fetchone()
        assert live_row is not None
        live = live_row[0][0]["Plan"]
        assert live["Node Type"] == "Index Scan"
        assert live["Index Name"] == "uq_tables_dataset_live_name"
        assert live["Actual Rows"] == 1
        historic = connection.execute("SELECT id FROM flyquery_tables WHERE name='table-9801'").fetchone()
        assert historic is not None
        history_row = connection.execute(
            "EXPLAIN (ANALYZE, FORMAT JSON) SELECT name FROM flyquery_tables WHERE id=%s", (historic[0],)
        ).fetchone()
        assert history_row is not None
        history = history_row[0][0]["Plan"]
        assert history["Node Type"] == "Index Scan"
        assert history["Index Name"] == "flyquery_tables_pkey"
        assert history["Actual Rows"] == 1


def test_runtime_role_keeps_tenant_isolation_and_local_name_uniqueness(source_database):
    target, role, engine = source_database
    upgrade(engine)
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    roles = _fixture.load("deploy/provision_roles.py")
    with psycopg.connect(uri) as owner:
        scope = dataset(owner)
        original = table(owner, scope)
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        roles.grant_table(owner, "flyquery_tables", role)
    with psycopg.connect(uri) as runtime:
        runtime.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        runtime.execute("SELECT set_config('app.tenant_id','tenant',true)")
        runtime.execute("SELECT set_config('app.workspace_id',%s,true)", (str(scope[1]),))
        staged = table(runtime, scope, active=False)
        with pytest.raises(psycopg.errors.UniqueViolation), runtime.transaction():
            table(runtime, scope)
        assert runtime.execute("SELECT id FROM flyquery_tables WHERE is_active").fetchall() == [(original,)]
        runtime.execute("SELECT set_config('app.tenant_id','other',true)")
        assert runtime.execute("SELECT id FROM flyquery_tables").fetchall() == []
        with pytest.raises(psycopg.errors.InsufficientPrivilege), runtime.transaction():
            table(runtime, scope, "forged")
        runtime.execute("SELECT set_config('app.tenant_id','tenant',true)")
        assert runtime.execute("SELECT is_active FROM flyquery_tables WHERE id=%s", (staged,)).fetchone() == (
            False,
        )


def test_standalone_alembic_entrypoint_upgrades_previous_head(source_database):
    target, _, engine = source_database
    config = Config(str(ROOT / "packages/structured/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "packages/structured/migrations"))
    config.set_main_option(
        "sqlalchemy.url", target.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)
    )
    command.upgrade(config, "0015_versioned_embedding_sets")
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        scope = dataset(connection)
        historical = table(connection, scope, active=False)
    command.upgrade(config, "head")
    with psycopg.connect(uri) as connection:
        replacement = table(connection, scope)
        assert connection.execute("SELECT id FROM flyquery_tables WHERE is_active").fetchall() == [
            (replacement,)
        ]
        assert connection.execute(
            "SELECT name FROM flyquery_tables WHERE id=%s", (historical,)
        ).fetchone() == ("orders",)


def test_lock_timeout_keeps_previous_constraint_and_can_retry(source_database):
    target, _, engine = source_database
    upgrade(engine, "0025_source_publication_baseline")
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as blocker:
        blocker.execute("LOCK TABLE flyquery_tables IN ACCESS EXCLUSIVE MODE")
        with pytest.raises(OperationalError, match="lock timeout"):
            upgrade(engine)
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT to_regclass('uq_tables_dataset_live_name')").fetchone() == (None,)
        assert connection.execute("SELECT version_num FROM koinon_structured_version").fetchone() == (
            "0025_source_publication_baseline",
        )
    upgrade(engine)
    with psycopg.connect(uri) as connection:
        scope = dataset(connection)
        historical = table(connection, scope, active=False)
        table(connection, scope)
        assert connection.execute(
            "SELECT name FROM flyquery_tables WHERE id=%s", (historical,)
        ).fetchone() == ("orders",)


def test_orm_sqlite_partial_index_allows_retained_name_but_rejects_two_live_rows():
    import sqlite3

    from flyquery.models.entities.table import Table
    from sqlalchemy.dialects.sqlite import dialect
    from sqlalchemy.schema import CreateIndex

    index = next(
        index
        for index in cast(SQLTable, Table.__table__).indexes
        if index.name == "uq_tables_dataset_live_name"
    )
    with sqlite3.connect(":memory:") as connection:
        connection.execute(
            "CREATE TABLE flyquery_tables(id TEXT, dataset_id TEXT, name TEXT, is_active BOOLEAN)"
        )
        connection.execute(str(CreateIndex(index).compile(dialect=dialect())))
        connection.execute("INSERT INTO flyquery_tables VALUES('old','dataset','orders',false)")
        connection.execute("INSERT INTO flyquery_tables VALUES('new','dataset','orders',true)")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO flyquery_tables VALUES('conflict','dataset','orders',true)")
        assert connection.execute("SELECT id FROM flyquery_tables WHERE is_active").fetchall() == [("new",)]
