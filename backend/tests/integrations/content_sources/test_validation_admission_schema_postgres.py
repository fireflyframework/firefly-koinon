# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reserve bounded preparation before provider proof without weakening retained evidence."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import psycopg
import pytest
from alembic import command
from psycopg import sql
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_concurrency_postgres import wait_for_blocked_connection
from test_source_migration_postgres import ROOT, load
from test_source_migration_postgres import source_database as source_database
from test_source_validation_schema_postgres import advance, begin, cleaning, entry, seal

pytestmark = pytest.mark.integration


def reserve(connection, **changes):
    return begin(
        connection,
        root_kind=None,
        root_proof_sha256=None,
        root_proof_ciphertext=None,
        **changes,
    )


def capture(connection, identifier, **changes):
    advance(
        connection,
        identifier,
        **{
            "root_captured": True,
            "root_kind": "folder",
            "root_proof_sha256": "d" * 64,
            "root_proof_ciphertext": b"encrypted-root",
            "checkpoint_ciphertext": b"encrypted-start",
            **changes,
        },
    )


async def test_reservation_precedes_root_proof_and_capture_is_once(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        identifier = reserve(connection)
        assert connection.execute(
            "SELECT root_captured,root_kind,root_proof_sha256,root_proof_ciphertext,revision "
            "FROM koinon_content_mapping_validations WHERE id=%s",
            (identifier,),
        ).fetchone() == (False, None, None, None, 1)
        capture(connection, identifier)
        assert connection.execute(
            "SELECT root_captured,root_kind,revision FROM koinon_content_mapping_validations WHERE id=%s",
            (identifier,),
        ).fetchone() == (True, "folder", 2)
        for changes in (
            {"root_captured": False},
            {"root_kind": "file"},
            {"root_proof_sha256": "e" * 64},
            {"root_proof_ciphertext": b"substituted"},
            {"request_sha256": "f" * 64},
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                advance(connection, identifier, **changes)


@pytest.mark.parametrize(
    "changes",
    [
        {"raw_observed_count": 1},
        {"eligible_count": 1},
        {"change_count": 1},
        {"verification_position": 1},
        {"enumeration_complete": True},
        {"checkpoint_ciphertext": b"unproved"},
        {"walk_ciphertext": b"unproved"},
        {"state": "verifying"},
        {"manifest_sha256": "e" * 64},
    ],
)
async def test_unproved_preparation_cannot_advance_or_enumerate(source_sessions, changes):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        identifier = reserve(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            advance(connection, identifier, **changes)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            entry(connection, identifier)


@pytest.mark.parametrize(
    "changes",
    [
        {"root_kind": None},
        {"root_proof_sha256": None},
        {"root_proof_ciphertext": None},
        {"checkpoint_ciphertext": None},
        {"walk_ciphertext": b"early-walk"},
        {"raw_observed_count": 1},
        {"session_hash": "foreign"},
        {"connection_revision": 2},
    ],
)
async def test_capture_requires_complete_proof_and_unchanged_identity(source_sessions, changes):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        identifier = reserve(connection)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            capture(connection, identifier, **changes)
        assert connection.execute(
            "SELECT root_captured,revision FROM koinon_content_mapping_validations WHERE id=%s",
            (identifier,),
        ).fetchone() == (False, 1)


@pytest.mark.parametrize("offset_microseconds", [-1, 0, 1])
async def test_capture_checks_database_time_at_immutable_expiry(
    source_sessions, source_database, offset_microseconds
):
    """Control only the clock in this fixture's isolated database, without sleeping."""
    _, uri = source_sessions
    _, runtime_role, _ = source_database
    roles = load("deploy/provision_roles.py")
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0].startswith("source_schema_")
        for table in ("koinon_content_mapping_validations", "koinon_content_mapping_validation_entries"):
            roles.grant_table(connection, table, runtime_role)
        identifier = reserve(connection)
        expires_at = connection.execute(
            "SELECT expires_at FROM koinon_content_mapping_validations WHERE id=%s", (identifier,)
        ).fetchone()[0]
        original = connection.execute(
            "SELECT pg_get_functiondef('public.koinon_guard_mapping_validation()'::regprocedure)"
        ).fetchone()[0]
        assert "clock_timestamp()" in original
        connection.execute(
            original.replace(
                "clock_timestamp()", "current_setting('koinon.test_validation_now')::timestamptz"
            )
        )
        connection.execute(
            "SELECT set_config('koinon.test_validation_now', %s, true)",
            ((expires_at + timedelta(microseconds=offset_microseconds)).isoformat(),),
        )
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime_role)))
        if offset_microseconds < 0:
            capture(connection, identifier)
            expected = (True, 2, expires_at)
        else:
            with (
                pytest.raises(psycopg.errors.CheckViolation, match="live empty reservation"),
                connection.transaction(),
            ):
                capture(connection, identifier)
            expected = (False, 1, expires_at)
        assert connection.execute(
            "SELECT root_captured,revision,expires_at FROM koinon_content_mapping_validations WHERE id=%s",
            (identifier,),
        ).fetchone() == expected


async def test_concurrent_last_slot_and_capture_serialize_without_rebinding(source_sessions):
    _, uri = source_sessions
    with psycopg.connect(uri) as writer:
        identifier = reserve(writer, max_active_per_tenant=1, max_active_per_owner=1)
        application = "root-reservation-" + uuid4().hex
        with psycopg.connect(uri, application_name=application) as other:
            waiter = asyncio.create_task(
                asyncio.to_thread(reserve, other, max_active_per_tenant=1, max_active_per_owner=1)
            )
            await wait_for_blocked_connection(uri, application)
            assert not waiter.done()
            writer.commit()
            with pytest.raises(psycopg.errors.CheckViolation, match="CAPACITY"):
                await waiter
            other.rollback()
            capture(writer, identifier)
            competing = asyncio.create_task(
                asyncio.to_thread(capture, other, identifier, root_proof_sha256="e" * 64)
            )
            await wait_for_blocked_connection(uri, application)
            writer.commit()
            with pytest.raises(psycopg.errors.CheckViolation):
                await competing
            other.rollback()
        assert writer.execute(
            "SELECT root_proof_sha256,revision FROM koinon_content_mapping_validations WHERE id=%s",
            (identifier,),
        ).fetchone() == ("d" * 64, 2)


@pytest.mark.parametrize("captured", [False, True])
async def test_cleanup_of_either_capture_phase_preserves_capacity_until_release(source_sessions, captured):
    _, uri = source_sessions
    with psycopg.connect(uri) as connection:
        identifier = reserve(connection, max_active_per_tenant=1, max_active_per_owner=1)
        if captured:
            capture(connection, identifier)
        cleaning(connection, identifier)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            capture(connection, identifier)
        with pytest.raises(psycopg.errors.CheckViolation, match="CAPACITY"), connection.transaction():
            reserve(connection, max_active_per_tenant=1, max_active_per_owner=1)
        advance(connection, identifier, state="abandoned", payload_released_at=datetime.now(UTC))
        assert connection.execute(
            "SELECT root_captured,root_proof_ciphertext,reserved_bytes=payload_bytes "
            "FROM koinon_content_mapping_validations WHERE id=%s",
            (identifier,),
        ).fetchone() == (captured, None, True)
        reserve(connection, max_active_per_tenant=1, max_active_per_owner=1)


def upgrade(engine, revision):
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, revision)
        connection.commit()


async def test_upgrade_preserves_proved_seal_and_cleaned_creation_identity(source_database):
    from koinon.integrations.content_sources.entities import PersonalSourceConnection

    target, _, engine = source_database
    upgrade(engine, "koinon_0054_mapping_validations")
    asynchronous = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    try:
        async with async_sessionmaker(asynchronous).begin() as session:
            session.add(
                PersonalSourceConnection(
                    id="connection",
                    tenant_id="retained",
                    owner="issuer|alice",
                    provider="google_drive",
                    status="connected",
                    revision=1,
                    external_subject="provider-alice",
                    issuer="https://accounts.google.com",
                    secret_ciphertext=b"encrypted-grant",
                )
            )
    finally:
        await asynchronous.dispose()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        sealed = begin(connection)
        entry(connection, sealed)
        seal(connection, sealed)
        cleaned = begin(connection)
        cleaning(connection, cleaned)
        advance(connection, cleaned, state="abandoned", payload_released_at=datetime.now(UTC))
        before = connection.execute(
            "SELECT id,to_jsonb(v) FROM koinon_content_mapping_validations v ORDER BY id"
        ).fetchall()
    upgrade(engine, "head")
    with psycopg.connect(uri) as connection:
        assert (
            connection.execute(
                "SELECT id,to_jsonb(v)-'root_captured' FROM koinon_content_mapping_validations v ORDER BY id"
            ).fetchall()
            == before
        )
        assert connection.execute(
            "SELECT bool_and(root_captured) FROM koinon_content_mapping_validations"
        ).fetchone() == (True,)
        fresh = reserve(connection)
        assert connection.execute(
            "SELECT root_captured FROM koinon_content_mapping_validations WHERE id=%s", (fresh,)
        ).fetchone() == (False,)
