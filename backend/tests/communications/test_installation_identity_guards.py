# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Stable installation identity admits row locking without allowing mutation."""

import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, MetaData, String, Table, create_engine, text
from sqlalchemy.exc import IntegrityError

from koinon.communications.entities import InstallationRecord


@pytest.fixture(params=["runtime", "migration"])
def identity(request):
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        if request.param == "runtime":
            InstallationRecord.__table__.create(connection)
        else:
            from pyfly.data.relational.sqlalchemy import UtcDateTime

            Table(
                "koinon_installation_identity",
                MetaData(),
                Column("singleton", String(16), primary_key=True),
                Column("installation_id", String(64), unique=True),
                Column("created_at", UtcDateTime()),
            ).create(connection)
            path = (
                Path(__file__).resolve().parents[3]
                / "deploy/migrations/native_versions/0030_communications.py"
            )
            spec = importlib.util.spec_from_file_location("identity_migration_guard", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with Operations.context(MigrationContext.configure(connection)):
                module.install_installation_guards()
        connection.execute(
            InstallationRecord.__table__.insert().values(
                singleton="installation", installation_id="stable-owned-uuid", created_at=datetime.now(UTC)
            )
        )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE koinon_installation_identity SET singleton=singleton",
        "UPDATE koinon_installation_identity SET installation_id='different'",
        "UPDATE koinon_installation_identity SET created_at=CURRENT_TIMESTAMP",
        "DELETE FROM koinon_installation_identity",
    ],
)
def test_runtime_and_migration_guards_reject_even_noop_identity_mutation(identity, statement):
    with pytest.raises(IntegrityError, match="immutable"), identity.begin() as connection:
        connection.execute(text(statement))
    with identity.connect() as connection:
        assert connection.execute(
            text("SELECT singleton,installation_id FROM koinon_installation_identity")
        ).one() == ("installation", "stable-owned-uuid")


def test_runtime_identity_has_one_canonical_singleton_key():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            InstallationRecord.__table__.create(connection)
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(
                InstallationRecord.__table__.insert().values(
                    singleton="other", installation_id="different", created_at=datetime.now(UTC)
                )
            )
    finally:
        engine.dispose()


def test_runtime_role_has_only_singleton_column_lock_privilege():
    path = Path(__file__).resolve().parents[3] / "deploy/provision_roles.py"
    spec = importlib.util.spec_from_file_location("installation_runtime_roles", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Statements:
        def __init__(self):
            self.items = []

        def execute(self, statement):
            self.items.append(statement.as_string())

    statements = Statements()
    module.grant_table(statements, "koinon_installation_identity", "example_runtime")
    assert statements.items == [
        'REVOKE ALL ON TABLE public."koinon_installation_identity" FROM "example_runtime"',
        'GRANT SELECT,INSERT ON TABLE public."koinon_installation_identity" TO "example_runtime"',
        "REVOKE UPDATE (singleton, installation_id, created_at) "
        'ON TABLE public."koinon_installation_identity" FROM "example_runtime"',
        'GRANT UPDATE (singleton) ON TABLE public."koinon_installation_identity" TO "example_runtime"',
    ]
