# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION = (
    Path(__file__).resolve().parents[3] / "deploy/migrations/native_versions/0022_organization_directory.py"
)


def test_additive_migration_creates_only_directory_tables_and_scoped_foreign_keys():
    assert MIGRATION.exists(), "Missing reserved additive organization migration"
    spec = importlib.util.spec_from_file_location("organization_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "koinon_0022_org_directory"
    assert module.down_revision == "koinon_0021_mcp_oauth_clients"
    engine = sa.create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id VARCHAR(64) PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE koinon_identity_providers "
            "(id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64) NOT NULL)"
        )
        operations = Operations(MigrationContext.configure(connection))
        old = module.op
        try:
            module.op = operations
            module.upgrade()
        finally:
            module.op = old
        inspector = sa.inspect(connection)
        assert "uq_identity_provider_tenant_id" in {
            index["name"] for index in inspector.get_indexes("koinon_identity_providers")
        }
        assert set(inspector.get_table_names()) == {
            "lattice_tenants",
            "koinon_identity_providers",
            "koinon_organization_units",
            "koinon_organization_people",
            "koinon_organization_directory_settings",
            "koinon_organization_profile_mappings",
        }
        for table in (
            "koinon_organization_units",
            "koinon_organization_people",
            "koinon_organization_profile_mappings",
        ):
            foreign_keys = inspector.get_foreign_keys(table)
            assert any(key["constrained_columns"] == ["tenant_id", "provider_id"] for key in foreign_keys)
        keys = inspector.get_foreign_keys("koinon_organization_people")
        assert any(key["constrained_columns"] == ["tenant_id", "manager_id"] for key in keys)
        assert any(key["constrained_columns"] == ["tenant_id", "unit_id"] for key in keys)
    engine.dispose()
