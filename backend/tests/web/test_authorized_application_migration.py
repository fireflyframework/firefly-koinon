# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError


def test_fixed_primary_migration_preserves_legacy_tokens_and_fences_purpose(tmp_path):
    path = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/native_versions/0016_authorized_applications.py"
    )
    spec = importlib.util.spec_from_file_location("applications_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "koinon_0016_authorized_apps" and len(module.revision) <= 32
    assert module.down_revision == "koinon_0015_mcp_authorization"
    engine = create_engine("sqlite:///" + str(tmp_path / "migration.db"))
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE lattice_tenants (id TEXT PRIMARY KEY)")
        connection.exec_driver_sql(
            "CREATE TABLE koinon_personal_tokens (id TEXT PRIMARY KEY,token_hash TEXT NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO koinon_personal_tokens VALUES ('retained','unchanged-digest')"
        )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        assert connection.exec_driver_sql(
            "SELECT id,token_hash,purpose,authorized_application_id FROM koinon_personal_tokens"
        ).all() == [("retained", "unchanged-digest", "personal", None)]
        columns = {
            column["name"] for column in inspect(connection).get_columns("koinon_authorized_applications")
        }
        assert columns == {
            "id",
            "subject",
            "client_id",
            "name",
            "resource",
            "tenant_id",
            "tenant_name",
            "workspace_id",
            "workspace_name",
            "scopes",
            "connected_at",
            "expires_at",
            "revoked_at",
            "last_used_at",
        }
        with pytest.raises(IntegrityError):
            connection.exec_driver_sql(
                "INSERT INTO koinon_personal_tokens(id,token_hash,purpose) "
                "VALUES ('invalid','digest','application')"
            )
