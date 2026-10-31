# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import ast
from pathlib import Path


def test_ciam_migration_is_additive_short_and_creates_only_two_tables():
    root = Path(__file__).resolve().parents[3]
    path = root / "deploy/migrations/native_versions/0023_corporate_profiles.py"
    assert path.is_file(), "Corporate profiles need their own additive migration"
    tree = ast.parse(path.read_text())
    values = {
        node.targets[0].id: ast.literal_eval(node.value)
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
    }
    assert values["revision"] == "koinon_0023_ciam_profiles"
    assert len(values["revision"]) <= 32
    assert values["down_revision"] == "koinon_0022_org_directory"
    created = [
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "create_table"
    ]
    assert set(created) == {
        "koinon_corporate_profile_snapshots",
        "koinon_organization_presentation_preferences",
    }
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"execute", "drop_table", "alter_column"}
        for node in ast.walk(tree)
    )


def test_migration_metadata_parity_with_tiny_sqlite_and_minimal_role_grants():
    import importlib.util
    from unittest.mock import patch

    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    from koinon.corporate_profiles.entities import (
        CorporateProfileSnapshot,
        OrganizationPresentationPreference,
    )

    root = Path(__file__).resolve().parents[3]
    spec = importlib.util.spec_from_file_location(
        "migration23", root / "deploy/migrations/native_versions/0023_corporate_profiles.py"
    )
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE koinon_organization_profile_mappings "
            "(tenant_id VARCHAR(64), provider_id VARCHAR(64))"
        )
        with patch.object(migration, "op", Operations(MigrationContext.configure(connection))):
            migration.upgrade()
        inspector = sa.inspect(connection)
        assert next(
            c
            for c in inspector.get_columns("koinon_organization_profile_mappings")
            if c["name"] == "profile_sync_json"
        )["nullable"]
        for entity in (CorporateProfileSnapshot, OrganizationPresentationPreference):
            actual = {c["name"]: c for c in inspector.get_columns(entity.__tablename__)}
            assert set(actual) == set(entity.__table__.columns.keys())
            for column in entity.__table__.columns:
                assert actual[column.name]["nullable"] == column.nullable
                assert str(actual[column.name]["type"]) == str(
                    column.type.compile(dialect=connection.dialect)
                )
        assert {
            u["name"] for u in inspector.get_unique_constraints(CorporateProfileSnapshot.__tablename__)
        } == {"uq_corporate_profile_owner", "uq_corporate_profile_external"}
        assert {
            c["name"] for c in inspector.get_check_constraints(CorporateProfileSnapshot.__tablename__)
        } == {"ck_corporate_profile_binding"}
    spec = importlib.util.spec_from_file_location("roles23", root / "deploy/provision_roles.py")
    roles = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(roles)

    class Recorder:
        def __init__(self):
            self.calls = []

        def execute(self, statement):
            self.calls.append(statement.as_string())

    for table in (CorporateProfileSnapshot.__tablename__, OrganizationPresentationPreference.__tablename__):
        recorder = Recorder()
        roles.grant_table(recorder, table, "inert_primary")
        assert len(recorder.calls) == 2 and recorder.calls[0].startswith("REVOKE ALL")
        assert recorder.calls[1].startswith("GRANT SELECT,INSERT,UPDATE ON")
        assert "DELETE" not in recorder.calls[1]
