# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in PostgreSQL role proof on a newly created, retained fixture database."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from psycopg import sql
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def pg_release():
    uri = os.environ.get("KOINON_ANSWER_RELEASE_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    suffix = uuid4().hex[:12]
    database, role = "answer_release_" + suffix, "answer_reader_" + suffix
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
        owner.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE").format(
                sql.Identifier(role)
            )
        )
    url = make_url(uri).set(database=database)
    with psycopg.connect(str(url), autocommit=True) as owner:
        owner.execute("CREATE TABLE answer_parent (id text PRIMARY KEY)")
        owner.execute("INSERT INTO answer_parent VALUES ('run')")
        owner.execute(
            "CREATE TABLE koinon_chat_tool_results (id text PRIMARY KEY, run_id text NOT NULL "
            "REFERENCES answer_parent(id) ON DELETE CASCADE, kind text NOT NULL, payload json NOT NULL)"
        )
        owner.execute(
            "INSERT INTO koinon_chat_tool_results VALUES ('retained','run','search','{\"original\":true}')"
        )
    migration_path = Path(__file__).parents[3] / "deploy/migrations/native_versions/0039_answer_release.py"
    spec = importlib.util.spec_from_file_location("answer_release_migration", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = create_engine(url.set(drivername="postgresql+psycopg"))
    with engine.begin() as connection, Operations.context(MigrationContext.configure(connection)):
        migration.upgrade()
    engine.dispose()
    spec = importlib.util.spec_from_file_location(
        "answer_release_privileges", Path(__file__).parents[3] / "deploy/provision_roles.py"
    )
    privileges = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(privileges)
    with psycopg.connect(str(url), autocommit=True) as owner:
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        privileges.grant_table(owner, "koinon_chat_tool_results", role)
        owner.execute(sql.SQL("GRANT SELECT,DELETE ON answer_parent TO {}").format(sql.Identifier(role)))
        owner.execute(
            "INSERT INTO koinon_chat_tool_results VALUES (%s,%s,%s,%s)",
            (
                "release",
                "run",
                "answer_release",
                Jsonb({"generation_id": "generation", "release": {"text_sha256": "original"}}),
            ),
        )
        assert owner.execute(
            "SELECT payload::jsonb FROM koinon_chat_tool_results WHERE id='retained'"
        ).fetchone()[0] == {"original": True}
    yield url, role


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE koinon_chat_tool_results SET payload='{}' WHERE id='release'",
        "UPDATE koinon_chat_tool_results SET kind='search' WHERE id='release'",
        "UPDATE koinon_chat_tool_results SET id='renamed' WHERE id='release'",
        "DELETE FROM koinon_chat_tool_results WHERE id='release'",
        "DELETE FROM answer_parent WHERE id='run'",
    ],
)
def test_postgres_runtime_cannot_mutate_or_cascade_delete_a_release(pg_release, statement):
    url, role = pg_release
    with psycopg.connect(str(url.set(username=role)), autocommit=True) as runtime:
        assert runtime.execute(
            "SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user"
        ).fetchone() == (False, False)
        with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
            runtime.execute(statement)
        assert (
            runtime.execute(
                "SELECT payload::jsonb FROM koinon_chat_tool_results WHERE id='release'"
            ).fetchone()[0]["release"]["text_sha256"]
            == "original"
        )
        assert runtime.execute("SELECT count(*) FROM answer_parent WHERE id='run'").fetchone()[0] == 1


def test_postgres_truncate_guard_survives_an_explicitly_overgranted_runtime(pg_release):
    url, role = pg_release
    with psycopg.connect(str(url), autocommit=True) as owner:
        owner.execute(
            sql.SQL("GRANT TRUNCATE ON koinon_chat_tool_results TO {}").format(sql.Identifier(role))
        )
    with psycopg.connect(str(url.set(username=role)), autocommit=True) as runtime:
        with pytest.raises(psycopg.errors.IntegrityConstraintViolation):
            runtime.execute("TRUNCATE koinon_chat_tool_results")
        assert (
            runtime.execute("SELECT count(*) FROM koinon_chat_tool_results WHERE id='release'").fetchone()[0]
            == 1
        )


def test_postgres_generation_uniqueness_and_mutable_tool_lifecycles(pg_release):
    url, role = pg_release
    with psycopg.connect(str(url.set(username=role)), autocommit=True) as runtime:
        with pytest.raises(psycopg.errors.UniqueViolation):
            runtime.execute(
                "INSERT INTO koinon_chat_tool_results VALUES "
                "('duplicate','run','answer_release','{\"generation_id\":\"generation\"}')"
            )
        runtime.execute(
            "INSERT INTO koinon_chat_tool_results VALUES "
            "('none','run','answer_release','{\"generation_id\":null}')"
        )
        with pytest.raises(psycopg.errors.UniqueViolation):
            runtime.execute(
                "INSERT INTO koinon_chat_tool_results VALUES ('duplicate-none','run','answer_release','{}')"
            )
        runtime.execute(
            "INSERT INTO koinon_chat_tool_results VALUES "
            "('retry','run','answer_release','{\"generation_id\":\"retry\"}')"
        )
        runtime.execute(
            "INSERT INTO koinon_chat_tool_results VALUES "
            "('next-refusal','run','answer_release','{\"generation_id\":null,\"reset_sequence\":7}')"
        )
        for payload in (
            {"generation_id": None, "reset_sequence": 7},
            {"generation_id": "generation", "reset_sequence": 7},
        ):
            with pytest.raises(psycopg.errors.UniqueViolation):
                runtime.execute(
                    "INSERT INTO koinon_chat_tool_results VALUES (%s,%s,%s,%s)",
                    ("context-duplicate", "run", "answer_release", Jsonb(payload)),
                )
        runtime.execute(
            "INSERT INTO koinon_chat_tool_results VALUES "
            "('proposal','run','proposal','{\"status\":\"pending\"}')"
        )
        runtime.execute(
            "UPDATE koinon_chat_tool_results SET payload='{\"status\":\"applied\"}' WHERE id='proposal'"
        )
        runtime.execute("DELETE FROM koinon_chat_tool_results WHERE id='proposal'")
        assert (
            runtime.execute(
                "SELECT count(*) FROM koinon_chat_tool_results WHERE kind='answer_release'"
            ).fetchone()[0]
            == 4
        )


def test_fresh_postgres_metadata_index_enforces_generation_and_reset_uniqueness():
    from sqlalchemy.dialects.postgresql import dialect
    from sqlalchemy.schema import CreateIndex

    from koinon.assistants.entities import ToolResult

    uri = os.environ.get("KOINON_ANSWER_RELEASE_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    database = "answer_metadata_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as owner:
        owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    url = make_url(uri).set(database=database)
    index = next(
        item for item in ToolResult.__table__.indexes if item.name == "uq_koinon_answer_release_generation"
    )
    with psycopg.connect(str(url), autocommit=True) as owner:
        owner.execute(
            "CREATE TABLE koinon_chat_tool_results "
            "(id text PRIMARY KEY,run_id text NOT NULL,kind text NOT NULL,payload json NOT NULL)"
        )
        owner.execute(str(CreateIndex(index).compile(dialect=dialect())))
        for identifier, payload in (
            ("generation", {"generation_id": "generation"}),
            ("refusal", {"generation_id": None}),
            ("retry-refusal", {"generation_id": None, "reset_sequence": 7}),
        ):
            owner.execute(
                "INSERT INTO koinon_chat_tool_results VALUES (%s,'run','answer_release',%s)",
                (identifier, Jsonb(payload)),
            )
        for payload in (
            {"generation_id": "generation", "reset_sequence": 7},
            {"generation_id": None},
            {"generation_id": None, "reset_sequence": 7},
        ):
            with pytest.raises(psycopg.errors.UniqueViolation):
                owner.execute(
                    "INSERT INTO koinon_chat_tool_results VALUES ('duplicate','run','answer_release',%s)",
                    (Jsonb(payload),),
                )
        owner.execute("INSERT INTO koinon_chat_tool_results VALUES ('ordinary','run','proposal','{}')")
        assert owner.execute("SELECT count(*) FROM koinon_chat_tool_results").fetchone()[0] == 4
