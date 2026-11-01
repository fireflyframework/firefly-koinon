# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "bootstrap_contacts_cli", Path(__file__).parents[1] / "bootstrap_contacts.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def value():
    return {
        "tenant_id": "example",
        "issuer": "https://login.microsoftonline.com/00000000-0000-4000-8000-000000000011/v2.0",
        "client_id": "configured-native-client",
        "entra_tenant_id": "00000000-0000-4000-8000-000000000011",
        "object_id": "00000000-0000-4000-8000-000000000012",
        "email": "admin@example.test",
        "display_name": "Admin",
        "source": "microsoft_graph_v1",
        "account_enabled": True,
        "user_type": "Member",
        "observed_at": datetime.now(UTC).isoformat(),
    }


def test_contact_file_requires_owner_only_regular_bounded_json(tmp_path):
    path = tmp_path / "contacts.json"
    path.write_text(json.dumps([value()]))
    path.chmod(0o600)
    assert module.load_contacts(path)[0].email == "admin@example.test"
    path.chmod(0o644)
    with pytest.raises(ValueError, match="owner-only"):
        module.load_contacts(path)
    path.chmod(0o600)
    path.write_text(json.dumps([value(), value()]))
    with pytest.raises(ValueError, match="once"):
        module.load_contacts(path)
    link = tmp_path / "link"
    link.symlink_to(path)
    with pytest.raises(OSError):
        module.load_contacts(link)


@pytest.mark.parametrize(
    "override",
    [
        {"email": "a@example.test\r\nBcc: attacker@example.test"},
        {"source": "request_header"},
        {"account_enabled": False},
        {"display_name": "Admin\nInjected"},
        {"user_type": "Guest"},
    ],
)
def test_contact_file_rejects_unverified_or_injected_delivery_fields(
    tmp_path, override
):
    path = tmp_path / "contacts.json"
    path.write_text(json.dumps([value() | override]))
    path.chmod(0o600)
    with pytest.raises(ValueError):
        module.load_contacts(path)


def test_new_migration_preserves_exact_contact_guards_without_importing_mutable_runtime():
    from koinon.communications.bootstrap_guards import contact_guards

    path = (
        Path(__file__).parents[1]
        / "migrations/native_versions/0035_bootstrap_welcome.py"
    )
    migration_spec = importlib.util.spec_from_file_location(
        "bootstrap_contact_migration", path
    )
    migration = importlib.util.module_from_spec(migration_spec)
    migration_spec.loader.exec_module(migration)
    assert migration.down_revision == "koinon_0034_postgres_cache"
    for dialect in ("sqlite", "postgresql"):
        assert migration.contact_guards(dialect) == contact_guards(dialect)
    with pytest.raises(RuntimeError, match="preserve"):
        migration.downgrade()


def test_additive_contact_migration_preserves_existing_rows_and_runtime_schema():
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from koinon.communications.entities import BootstrapContactRecord
    from pyfly.data.relational.sqlalchemy import Base

    path = (
        Path(__file__).parents[1]
        / "migrations/native_versions/0035_bootstrap_welcome.py"
    )
    migration_spec = importlib.util.spec_from_file_location(
        "bootstrap_contact_upgrade", path
    )
    migration = importlib.util.module_from_spec(migration_spec)
    migration_spec.loader.exec_module(migration)
    dependencies = {
        key.column.table for key in BootstrapContactRecord.__table__.foreign_keys
    }
    while (
        missing := {
            key.column.table for table in dependencies for key in table.foreign_keys
        }
        - dependencies
    ):
        dependencies.update(missing)
    engine = sa.create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            Base.metadata.create_all(connection, tables=list(dependencies))
            connection.exec_driver_sql(
                "CREATE TABLE retained_original (id TEXT PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO retained_original VALUES ('preserved-original')"
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
            assert (
                connection.exec_driver_sql(
                    "SELECT id FROM retained_original"
                ).scalar_one()
                == "preserved-original"
            )
            actual = {
                column["name"]: column
                for column in sa.inspect(connection).get_columns(
                    BootstrapContactRecord.__tablename__
                )
            }
            assert set(actual) == set(BootstrapContactRecord.__table__.columns.keys())
            for column in BootstrapContactRecord.__table__.columns:
                assert actual[column.name]["nullable"] == column.nullable
    finally:
        engine.dispose()
