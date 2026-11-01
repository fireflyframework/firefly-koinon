# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Runtime metadata and additive migration enforce the same permanent enrollment receipt."""

import importlib.util
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from koinon.bootstrap.entities import ACTIVATION_COLUMNS, IMMUTABLE_COLUMNS, BootstrapIdentityGrant
from koinon.catalog.entities import Membership, Tenant


def migration():
    path = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/native_versions/0033_bootstrap_identity_grants.py"
    )
    spec = importlib.util.spec_from_file_location("bootstrap_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["runtime", "migration"])
def database(request):
    engine = sa.create_engine("sqlite://", hide_parameters=True)
    with engine.begin() as connection:
        Tenant.__table__.create(connection)
        Membership.__table__.create(connection)
        if request.param == "runtime":
            BootstrapIdentityGrant.__table__.create(connection)
        else:
            with Operations.context(MigrationContext.configure(connection)):
                migration().upgrade()
        connection.execute(Tenant.__table__.insert().values(id="org", name="Retained organization"))
        connection.execute(
            Membership.__table__.insert().values(
                id="member", tenant_id="org", subject="https://issuer.invalid|verified-sub", role="admin"
            )
        )
        connection.execute(
            BootstrapIdentityGrant.__table__.insert().values(
                id="grant",
                tenant_id="org",
                canonical_issuer="https://issuer.invalid",
                native_client_id="client",
                entra_tenant_id="tid",
                object_id="oid",
                role="admin",
                created_at=datetime.now(UTC) - timedelta(days=1),
                expires_at=datetime.now(UTC) + timedelta(days=1),
            )
        )
    try:
        yield engine
    finally:
        engine.dispose()


ACTIVATE = (
    "consumed_at=CURRENT_TIMESTAMP, consumed_subject='https://issuer.invalid|verified-sub', "
    "membership_id='member'"
)


@pytest.mark.parametrize(
    "changed",
    [
        "id='different'",
        "tenant_id='different'",
        "canonical_issuer='https://changed.invalid'",
        "native_client_id='different'",
        "entra_tenant_id='different'",
        "object_id='different'",
        "role='viewer'",
        "expires_at=datetime(expires_at,'+1 day')",
        "created_at=datetime(created_at,'-1 day')",
    ],
)
def test_pending_identity_cannot_change_even_during_otherwise_valid_activation(database, changed):
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(sa.text(f"UPDATE koinon_bootstrap_identity_grants SET {ACTIVATE}, {changed}"))
    with database.connect() as connection:
        assert (
            connection.execute(sa.text("SELECT consumed_at FROM koinon_bootstrap_identity_grants")).scalar()
            is None
        )


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE koinon_bootstrap_identity_grants SET consumed_at=CURRENT_TIMESTAMP",
        "UPDATE koinon_bootstrap_identity_grants SET consumed_at=CURRENT_TIMESTAMP, "
        "consumed_subject='https://issuer.invalid|forged', membership_id='member'",
        "DELETE FROM koinon_bootstrap_identity_grants",
    ],
)
def test_partial_activation_wrong_member_and_deletion_fail_closed(database, statement):
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(sa.text(statement))


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE koinon_bootstrap_identity_grants SET consumed_at=NULL, "
        "consumed_subject=NULL, membership_id=NULL",
        "UPDATE koinon_bootstrap_identity_grants SET consumed_at=consumed_at",
        "UPDATE koinon_bootstrap_identity_grants SET membership_id='new-member'",
        "DELETE FROM koinon_bootstrap_identity_grants",
    ],
)
def test_consumed_receipt_cannot_reset_mutate_or_delete_after_membership_removal(database, statement):
    with database.begin() as connection:
        connection.execute(sa.text(f"UPDATE koinon_bootstrap_identity_grants SET {ACTIVATE}"))
        connection.execute(sa.text("DELETE FROM lattice_memberships WHERE id='member'"))
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(sa.text(statement))
    with database.connect() as connection:
        assert (
            connection.execute(sa.text("SELECT membership_id FROM koinon_bootstrap_identity_grants")).scalar()
            == "member"
        )


def test_additive_migration_matches_native_table_and_retains_existing_data(database):
    module = migration()
    assert (module.revision, module.down_revision) == ("koinon_0033_bootstrap", "koinon_0032_large_files")
    with database.connect() as connection:
        assert (
            connection.execute(sa.text("SELECT name FROM lattice_tenants")).scalar()
            == "Retained organization"
        )
        actual = sa.inspect(connection).get_columns(BootstrapIdentityGrant.__tablename__)
        assert [(column["name"], column["nullable"]) for column in actual] == [
            (column.name, column.nullable) for column in BootstrapIdentityGrant.__table__.columns
        ]
        assert set(IMMUTABLE_COLUMNS) | set(ACTIVATION_COLUMNS) == {column["name"] for column in actual}
    with pytest.raises(RuntimeError, match="preserve consumed"):
        module.downgrade()


def test_database_clock_rejects_expired_grant_activation(database):
    with database.begin() as connection:
        connection.execute(
            BootstrapIdentityGrant.__table__.insert().values(
                id="expired",
                tenant_id="org",
                canonical_issuer="https://issuer.invalid",
                native_client_id="client",
                entra_tenant_id="tid",
                object_id="expired-oid",
                role="admin",
                created_at=datetime.now(UTC) - timedelta(days=2),
                expires_at=datetime.now(UTC) - timedelta(days=1),
            )
        )
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(
            sa.text(f"UPDATE koinon_bootstrap_identity_grants SET {ACTIVATE} WHERE id='expired'")
        )


def test_native_and_frozen_postgres_guard_use_fixed_catalog_and_real_membership_schema():
    from koinon.bootstrap.entities import guard_statements

    native = guard_statements("postgresql")
    assert migration().guard_statements("postgresql") == native
    assert "SET search_path=pg_catalog" in native[0]
    assert "FROM public.lattice_memberships" in native[0]
