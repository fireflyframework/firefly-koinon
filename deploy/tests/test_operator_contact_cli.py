# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from koinon.catalog.entities import Tenant
from koinon.communications.contact_entities import OperatorContactRecord
from koinon.communications.contact_guards import contact_guards
from psycopg import sql
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

ROOT = Path(__file__).parents[1]


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


cli = module(ROOT / "communications.py", "operator_contacts_cli")
migration = module(
    ROOT / "migrations/native_versions/0038_operator_contacts.py",
    "operator_contacts_38",
)
roles = module(ROOT / "provision_roles.py", "operator_contact_roles")


def observation():
    now = datetime.now(UTC)
    return {
        "tenant_id": "north",
        "identity": {
            "kind": "keycloak",
            "issuer": "https://issuer.test",
            "client_id": "client",
            "external_subject": "immutable-user",
        },
        "email": "private@example.test",
        "display_name": "Approved contact",
        "source": "keycloak_admin",
        "account_enabled": None,
        "observed_at": now.isoformat(),
        "expires_at": (now + timedelta(hours=1)).isoformat(),
    }


def test_protected_contact_file_is_bounded_owner_only_and_rejects_duplicates_and_links(
    tmp_path,
):
    path = tmp_path / "contacts.json"
    value = observation()
    path.write_text(json.dumps([value]))
    path.chmod(0o600)
    assert cli.load_contacts(path)[0].account_enabled is None
    path.chmod(0o644)
    with pytest.raises(ValueError, match="owner-only"):
        cli.load_contacts(path)
    path.chmod(0o600)
    path.write_text(json.dumps([value, value]))
    with pytest.raises(ValueError, match="once"):
        cli.load_contacts(path)
    link = tmp_path / "linked"
    link.symlink_to(path)
    with pytest.raises(OSError):
        cli.load_contacts(link)


def test_diagnostic_cli_cannot_accept_an_owner_or_email_and_requires_operation_uuid():
    identifier = str(uuid4())
    for extra in (["--email", "other@example.test"], ["--owner", "invented"]):
        with pytest.raises(SystemExit):
            cli.arguments(
                [
                    "diagnostic",
                    "--contact-id",
                    identifier,
                    "--operation-id",
                    identifier,
                    *extra,
                ]
            )
    with pytest.raises(SystemExit):
        cli.arguments(["diagnostic", "--contact-id", identifier])
    args = cli.arguments(
        ["diagnostic", "--contact-id", identifier, "--operation-id", identifier]
    )
    assert str(args.contact_id) == str(args.operation_id) == identifier


def test_migration_is_frozen_and_matches_current_metadata_guards():
    assert migration.revision == "koinon_0038_operator_contacts"
    assert migration.down_revision == "koinon_0037_system_spaces"
    for dialect in ("postgresql", "sqlite"):
        assert migration.contact_guards(dialect) == contact_guards(dialect)
    with pytest.raises(RuntimeError, match="reviewed restore"):
        migration.downgrade()


@pytest.fixture(scope="module")
def owned_postgres():
    uri = os.environ.get("KOINON_CONTACT_TEST_PG_URL") or os.environ.get(
        "KOINON_INSTALLATION_ANN_TEST_PG_URL"
    )
    if not uri:
        pytest.skip("Requires an explicitly owned PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port not in {None, 18783}
    suffix = uuid4().hex[:12]
    database, runtime = "contact_" + suffix, "contact_runtime_" + suffix
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database))
        )
        connection.execute(
            sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(runtime)
            )
        )
    target = base.set(database=database)
    engine = create_engine(target.set(drivername="postgresql+psycopg"))
    with engine.begin() as connection:
        Tenant.__table__.create(connection)
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
    connection = psycopg.connect(
        target.set(drivername="postgresql").render_as_string(hide_password=False),
        autocommit=True,
    )
    connection.execute(
        "INSERT INTO lattice_tenants(id,name,created_at) VALUES ('north','North',clock_timestamp())"
    )
    connection.execute(
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(runtime))
    )
    roles.grant_table(connection, OperatorContactRecord.__tablename__, runtime)
    with connection.transaction():
        row = connection.execute(
            "SELECT column_name,data_type,is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='koinon_operator_delivery_contacts' ORDER BY ordinal_position"
        ).fetchall()
    assert [column[0] for column in row] == list(
        OperatorContactRecord.__table__.columns.keys()
    )
    yield connection, runtime, database
    connection.close()
    engine.dispose()
    # Fixture databases and roles are retained for the independent migration/privilege receipt.


@pytest.mark.integration
def test_actual_postgres_migration_and_runtime_columns_deny_reseed_renew_revoke_delete(
    owned_postgres,
):
    connection, runtime, _ = owned_postgres
    identifier = str(uuid4())
    connection.execute(
        "INSERT INTO koinon_operator_delivery_contacts(id,tenant_id,identity_key,identity_json,contact_ciphertext,revision,created_at,observed_at,expires_at) VALUES (%s,'north',%s,'{}','opaque',1,clock_timestamp(),clock_timestamp(),clock_timestamp()+interval '1 hour')",
        (identifier, identifier),
    )
    for statement in (
        "INSERT INTO koinon_operator_delivery_contacts SELECT * FROM koinon_operator_delivery_contacts",
        "UPDATE koinon_operator_delivery_contacts SET contact_ciphertext='retargeted'",
        "UPDATE koinon_operator_delivery_contacts SET identity_json='{}'",
        "UPDATE koinon_operator_delivery_contacts SET revision=revision+1",
        "UPDATE koinon_operator_delivery_contacts SET revoked_at=clock_timestamp()",
        "DELETE FROM koinon_operator_delivery_contacts",
        "TRUNCATE koinon_operator_delivery_contacts",
    ):
        with (
            pytest.raises(psycopg.errors.InsufficientPrivilege),
            connection.transaction(),
        ):
            connection.execute(
                sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime))
            )
            connection.execute(statement)
    with connection.transaction():
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime)))
        assert (
            connection.execute(
                "SELECT count(*) FROM koinon_operator_delivery_contacts"
            ).fetchone()[0]
            == 1
        )
        connection.execute(
            "UPDATE koinon_operator_delivery_contacts SET canonical_subject='https://issuer.test|signed-user',binding_ciphertext='opaque-proof',bound_at=clock_timestamp() WHERE id=%s",
            (identifier,),
        )
    with (
        pytest.raises(psycopg.errors.IntegrityConstraintViolation),
        connection.transaction(),
    ):
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(runtime)))
        connection.execute(
            "UPDATE koinon_operator_delivery_contacts SET canonical_subject='different',binding_ciphertext='changed',bound_at=clock_timestamp() WHERE id=%s",
            (identifier,),
        )


@pytest.mark.integration
def test_actual_postgres_operator_revision_is_monotonic_and_identity_cannot_change(
    owned_postgres,
):
    connection, _, _ = owned_postgres
    identifier = connection.execute(
        "SELECT id FROM koinon_operator_delivery_contacts LIMIT 1"
    ).fetchone()[0]
    connection.execute(
        "UPDATE koinon_operator_delivery_contacts SET revision=revision+1,contact_ciphertext='fresh-approved-observation' WHERE id=%s",
        (identifier,),
    )
    for statement in (
        "UPDATE koinon_operator_delivery_contacts SET revision=1",
        "UPDATE koinon_operator_delivery_contacts SET revision=revision+1,identity_key='new-identity'",
        "UPDATE koinon_operator_delivery_contacts SET canonical_subject=NULL,binding_ciphertext=NULL,bound_at=NULL",
        "DELETE FROM koinon_operator_delivery_contacts",
        "TRUNCATE koinon_operator_delivery_contacts",
    ):
        with (
            pytest.raises(psycopg.errors.IntegrityConstraintViolation),
            connection.transaction(),
        ):
            connection.execute(statement)
    connection.execute(
        "UPDATE koinon_operator_delivery_contacts SET revision=revision+1,revoked_at=clock_timestamp() WHERE id=%s",
        (identifier,),
    )
    with (
        pytest.raises(psycopg.errors.IntegrityConstraintViolation),
        connection.transaction(),
    ):
        connection.execute(
            "UPDATE koinon_operator_delivery_contacts SET revision=revision+1,revoked_at=NULL WHERE id=%s",
            (identifier,),
        )


@pytest.mark.integration
def test_actual_postgres_contact_operator_is_distinct_from_signed_binding_runtime(
    owned_postgres,
):
    connection, _, _ = owned_postgres
    operator = "contact_operator_" + uuid4().hex[:12]
    connection.execute(
        sql.SQL("CREATE ROLE {} NOLOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS").format(
            sql.Identifier(operator)
        )
    )
    connection.execute(
        sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(operator))
    )
    roles.grant_contact_operator(connection, operator, dependencies=False)
    observed = connection.execute(
        "SELECT has_table_privilege(%s,'public.koinon_operator_delivery_contacts','INSERT'),"
        "has_column_privilege(%s,'public.koinon_operator_delivery_contacts','revision','UPDATE'),"
        "has_column_privilege(%s,'public.koinon_operator_delivery_contacts','canonical_subject','UPDATE'),"
        "has_table_privilege(%s,'public.koinon_operator_delivery_contacts','DELETE')",
        (operator,) * 4,
    ).fetchone()
    assert observed == (True, True, False, False)
    with pytest.raises(psycopg.errors.InsufficientPrivilege), connection.transaction():
        connection.execute(
            sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(operator))
        )
        connection.execute(
            "UPDATE koinon_operator_delivery_contacts SET canonical_subject='forged'"
        )

    connection.execute(
        sql.SQL("ALTER ROLE {} INHERIT").format(sql.Identifier(operator))
    )
    with pytest.raises(ValueError, match="NOINHERIT"):
        roles.check_contact_operator(connection, operator, dependencies=False)
    connection.execute(
        sql.SQL("ALTER ROLE {} NOINHERIT").format(sql.Identifier(operator))
    )
    connection.execute(
        sql.SQL("GRANT {} TO {}").format(
            sql.Identifier(owned_postgres[1]), sql.Identifier(operator)
        )
    )
    with pytest.raises(ValueError, match="parents"):
        roles.check_contact_operator(connection, operator, dependencies=False)
    connection.execute(
        sql.SQL("REVOKE {} FROM {}").format(
            sql.Identifier(owned_postgres[1]), sql.Identifier(operator)
        )
    )
    connection.execute(
        sql.SQL(
            "GRANT UPDATE(canonical_subject) ON koinon_operator_delivery_contacts TO {}"
        ).format(sql.Identifier(operator))
    )
    with pytest.raises(RuntimeError, match="column"):
        roles.check_contact_operator(connection, operator, dependencies=False)
    connection.execute(
        sql.SQL(
            "REVOKE UPDATE(canonical_subject) ON koinon_operator_delivery_contacts FROM {}"
        ).format(sql.Identifier(operator))
    )
    roles.check_contact_operator(connection, operator, dependencies=False)
