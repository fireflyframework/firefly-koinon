# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit owned PostgreSQL only; fixture databases and evidence are retained."""

import asyncio
import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import test_email_invitations as fixtures
from alembic import command
from psycopg import sql
from pyfly.data.transaction.registry import TransactionManagerRegistry, bind_registry
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from test_native_delivery_flow import owned_transport
from test_welcome_recovery import prepared, request

from koinon.communications.outbox import CommunicationOutbox
from koinon.communications.recovery_entities import WelcomeRecoveryRecord
from koinon.communications.repositories import OutboxRepository
from koinon.communications.submission import EmailSubmission

ROOT = Path(__file__).parents[3]
spec = importlib.util.spec_from_file_location("recovery_native_migrations", ROOT / "deploy/migrate.py")
migrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(migrate)
spec = importlib.util.spec_from_file_location("recovery_native_roles", ROOT / "deploy/provision_roles.py")
roles = importlib.util.module_from_spec(spec)
spec.loader.exec_module(roles)


@pytest.fixture
async def pg_email(tmp_path, monkeypatch):
    uri = os.environ.get("KOINON_EMAIL_RECOVERY_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    base = make_url(uri)
    unix = (
        str(base.query.get("host", "")).startswith("/tmp/koinon-bulk-pg-")
        and str(base.query.get("port")) == "65432"
    )
    assert unix or base.host == "127.0.0.1" and base.port not in (None, 18783)
    suffix = uuid4().hex[:12]
    database = "email_recovery_" + suffix
    with psycopg.connect(uri, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database))
        )
    target = base.set(database=database)
    engine = create_engine(target.set(drivername="postgresql+psycopg"))

    def upgrade(revision):
        with engine.connect() as connection:
            config = migrate.history_config("native", ROOT / "deploy/migrations/native_versions", connection)
            command.upgrade(config, revision)
            connection.commit()

    upgrade("koinon_0040_bulk_pinned")
    real_config = fixtures.Config

    def configured(values):
        relational = values["pyfly"]["data"]["relational"]
        relational.update(
            url=target.set(drivername="postgresql+psycopg").render_as_string(hide_password=False),
            **{"ddl-auto": "none"},
        )
        return real_config(values)

    monkeypatch.setattr(fixtures, "Config", configured)
    generator = fixtures.email_context.__wrapped__(tmp_path)
    context, directory = await anext(generator)
    try:
        authority, target_contact, original = await prepared(context, correlate=True)
        with engine.connect() as connection:
            before = connection.exec_driver_sql(
                "SELECT to_jsonb(o)::text FROM koinon_communication_outbox o WHERE id=%s", (original.id,)
            ).scalar_one()
        upgrade("koinon_0041_email_recovery")
        from koinon.communications.observation_entities import (
            DeliveryBindingRecord,
            DeliveryInspectionRecord,
            DeliveryObservationRecord,
        )

        with engine.connect() as connection:
            for model in (
                WelcomeRecoveryRecord,
                DeliveryBindingRecord,
                DeliveryInspectionRecord,
                DeliveryObservationRecord,
            ):
                names = (
                    connection.exec_driver_sql(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=%s ORDER BY ordinal_position",
                        (model.__tablename__,),
                    )
                    .scalars()
                    .all()
                )
                assert names == list(model.__table__.c.keys())
        with engine.connect() as connection:
            assert (
                connection.exec_driver_sql(
                    "SELECT to_jsonb(o)::text FROM koinon_communication_outbox o WHERE id=%s", (original.id,)
                ).scalar_one()
                == before
            )
        yield context, directory, authority, target_contact, original, target, engine
    finally:
        await generator.aclose()
        engine.dispose()
        # This new owned database and roles remain available for independent review.


@pytest.mark.integration
async def test_actual_postgres_same_key_concurrency_admits_one_new_delivery_preserving_unknown(
    pg_email, monkeypatch
):
    context, directory, service, target, original, _, _ = pg_email
    key = str(uuid4())
    body = request(original, target)
    registry = context.get_bean(TransactionManagerRegistry)

    async def admit():
        with bind_registry(registry):
            return await service.operator_recover(original.id, body, key)

    reached = asyncio.Event()
    arrivals = 0
    native_lock = service.catalog._lock_tenant

    async def simultaneous_lock(tenant_id):
        nonlocal arrivals
        arrivals += 1
        if arrivals == 2:
            reached.set()
        await reached.wait()
        return await native_lock(tenant_id)

    monkeypatch.setattr(service.catalog, "_lock_tenant", simultaneous_lock)
    async with asyncio.timeout(10):
        first, second = await asyncio.gather(admit(), admit())
    monkeypatch.setattr(service.catalog, "_lock_tenant", native_lock)
    assert first.delivery_id == second.delivery_id != original.id
    assert len(await service.records.find_all(original_delivery_id=original.id)) == 1
    messages = owned_transport(context)
    state = context.get_bean(CommunicationOutbox)
    await context.get_bean(EmailSubmission).execute(await state.claim("pg-recovery"))
    assert len(messages) == 1 and directory.reads == 0
    saved = await context.get_bean(OutboxRepository).find_by_id(original.id)
    assert (
        saved.status == "unknown" and saved.attempt_count == 1 and saved.payload_hash == original.payload_hash
    )


@pytest.mark.integration
async def test_actual_postgres_immutable_evidence_and_runtime_operator_forgery_denied(pg_email):
    context, _, service, target, original, url, engine = pg_email
    await service.operator_recover(original.id, request(original, target), str(uuid4()))
    from pyfly.notifications import EmailStatus
    from test_email_invitations import ACTOR
    from test_operation_observations import Provider, observation_service

    observations = await observation_service(context, service, Provider(EmailStatus.SENT))
    await observations.bind_legacy(original.id, original.provider_reference, "a" * 64)
    await observations.inspect(ACTOR, "north", original.id, original.generation, str(uuid4()))
    runtime = "email_recovery_runtime_" + uuid4().hex[:12]
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(runtime)
            )
        )
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(runtime)))
        tables = (
            "koinon_welcome_recoveries",
            "koinon_email_provider_bindings",
            "koinon_email_operation_inspections",
            "koinon_email_operation_observations",
        )
        for table in tables:
            connection.execute(
                sql.SQL("GRANT UPDATE(id) ON public.{} TO {}").format(
                    sql.Identifier(table), sql.Identifier(runtime)
                )
            )
            roles.grant_table(connection, table, runtime)
            assert connection.execute(
                "SELECT has_any_column_privilege(%s,%s,'UPDATE')", (runtime, "public." + table)
            ).fetchone() == (False,)
        for table in tables:
            for action in (
                "UPDATE " + table + " SET tenant_id='changed'",
                "DELETE FROM " + table,
                "TRUNCATE " + table + " CASCADE",
            ):
                with (
                    pytest.raises(psycopg.errors.IntegrityConstraintViolation) as guard_error,
                    connection.transaction(force_rollback=True),
                ):
                    connection.execute(action)
                assert guard_error.value.sqlstate == "23000"
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction(force_rollback=True):
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime)))
            connection.execute(
                "INSERT INTO koinon_email_provider_bindings("
                "id,tenant_id,provider,instance_sha256,operation_id,source,evidence_sha256,created_at) "
                "VALUES(%s,'north','azure-communication-email',%s,%s,'operator_historical',%s,clock_timestamp())",
                (original.id, "a" * 64, original.id, "b" * 64),
            )
        with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction(force_rollback=True):
            connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime)))
            connection.execute("UPDATE koinon_welcome_recoveries SET reason='changed'")


@pytest.mark.integration
@pytest.mark.parametrize("drift", [False, True])
async def test_actual_limited_operator_admits_new_delivery_without_outbox_update_privilege(
    pg_email, monkeypatch, drift
):
    from pyfly.data.transaction import TransactionTemplate
    from pyfly.kernel import ConflictException
    from sqlalchemy import text

    context, _, service, target, original, url, _ = pg_email
    operator = "email_recovery_operator_" + uuid4().hex[:10]
    with psycopg.connect(
        url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
    ) as connection:
        connection.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(operator)
            )
        )
        connection.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(operator)))
        roles.grant_contact_operator(connection, operator)
        assert connection.execute(
            "SELECT has_any_column_privilege(%s,'public.koinon_communication_outbox','UPDATE')", (operator,)
        ).fetchone() == (False,)
    cli_spec = importlib.util.spec_from_file_location(
        "limited_operator_cli", ROOT / "deploy/communications.py"
    )
    cli = importlib.util.module_from_spec(cli_spec)
    cli_spec.loader.exec_module(cli)
    args = cli.arguments(
        [
            "welcome-recovery",
            "--delivery-id",
            original.id,
            "--contact-id",
            target.id,
            "--expected-generation",
            str(original.generation),
            "--expected-contact-revision",
            str(target.revision),
            "--operation-id",
            str(uuid4()),
            "--reason",
            "recipient_reported_not_received",
            "--acknowledge-possible-duplicate",
        ]
    )
    registry = context.get_bean(TransactionManagerRegistry)
    status_args = cli.arguments(
        ["welcome-recovery-status", "--delivery-id", original.id, "--contact-id", target.id]
    )
    async with TransactionTemplate(registry.get("primary")).transaction():
        await service.records._require_session().execute(text('SET LOCAL ROLE "' + operator + '"'))
        metadata = await cli.execute(context, status_args)
    assert metadata["generation"] == original.generation and metadata["contact_revision"] == target.revision
    assert metadata["can_recover_welcome"] is True and "email" not in metadata
    if drift:
        recipient = service._recipient

        async def concurrent_generation_change(*args, **kwargs):
            value = await recipient(*args, **kwargs)

            def update():
                with psycopg.connect(
                    url.set(drivername="postgresql").render_as_string(hide_password=False), autocommit=True
                ) as connection:
                    connection.execute(
                        "UPDATE koinon_communication_outbox SET generation=generation+1 WHERE id=%s",
                        (original.id,),
                    )

            async with asyncio.timeout(3):
                await asyncio.to_thread(update)
            return value

        monkeypatch.setattr(service, "_recipient", concurrent_generation_change)
    registry = context.get_bean(TransactionManagerRegistry)

    async def invoke():
        async with TransactionTemplate(registry.get("primary")).transaction():
            await service.records._require_session().execute(text('SET LOCAL ROLE "' + operator + '"'))
            return await cli.execute(context, args)

    if drift:
        with pytest.raises(ConflictException) as changed:
            await invoke()
        assert changed.value.code == "WELCOME_RECOVERY_CHANGED"
        assert not await service.records.find_all()
    else:
        admitted = await invoke()
        assert admitted["delivery_id"] != original.id
        original.generation += 1
        await context.get_bean(OutboxRepository).save(original)
        messages = owned_transport(context)
        await context.get_bean(EmailSubmission).execute(
            await context.get_bean(CommunicationOutbox).claim("stale-queued-recovery")
        )
        assert messages == []
        assert (
            await context.get_bean(OutboxRepository).find_by_id(admitted["delivery_id"])
        ).status == "cancelled"
    saved = await context.get_bean(OutboxRepository).find_by_id(original.id)
    assert saved.status == "unknown" and saved.attempt_count == 1
