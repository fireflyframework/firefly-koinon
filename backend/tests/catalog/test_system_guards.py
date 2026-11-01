# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""System spaces remain protected even outside ordinary catalog service calls."""

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from koinon.catalog.entities import CatalogEntry, Tenant


def migration():
    path = Path(__file__).resolve().parents[3] / "deploy/migrations/native_versions/0037_system_spaces.py"
    spec = importlib.util.spec_from_file_location("system_spaces_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=["runtime", "migration"])
def database(request):
    engine = sa.create_engine("sqlite://", hide_parameters=True)
    with engine.begin() as connection:
        Tenant.__table__.create(connection)
        connection.execute(Tenant.__table__.insert().values(id="org", name="Retained organization"))
        if request.param == "runtime":
            CatalogEntry.__table__.create(connection)
        else:
            connection.execute(
                sa.text(
                    "CREATE TABLE lattice_catalog (id VARCHAR(64) PRIMARY KEY, tenant_id VARCHAR(64), "
                    "kind VARCHAR(32), name VARCHAR(255), parent_id VARCHAR(64), workspace_id VARCHAR(64), "
                    "project_id VARCHAR(64), status VARCHAR(32), metadata_json JSON, "
                    "description VARCHAR(4000), "
                    "created_by VARCHAR(512), updated_by VARCHAR(512), "
                    "created_at DATETIME, updated_at DATETIME)"
                )
            )
            connection.execute(
                sa.text(
                    "INSERT INTO lattice_catalog(id,tenant_id,kind,name,workspace_id,status) "
                    "VALUES('retained','org','workspace','Retained user space','retained','ready')"
                )
            )
            with Operations.context(MigrationContext.configure(connection)):
                migration().upgrade()
        connection.execute(
            CatalogEntry.__table__.insert().values(
                id="system",
                tenant_id="org",
                kind="workspace",
                name="Organization",
                workspace_id="system",
                created_by="system:installation",
                system_key="organization",
                installation_run_id="run",
            )
        )
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.mark.parametrize(
    "statement",
    [
        "DELETE FROM lattice_catalog WHERE id='system'",
        "UPDATE lattice_catalog SET system_key=NULL WHERE id='system'",
        "UPDATE lattice_catalog SET installation_run_id=NULL WHERE id='system'",
        "UPDATE lattice_catalog SET status='archived' WHERE id='system'",
        "UPDATE lattice_catalog SET parent_id='another' WHERE id='system'",
        "UPDATE lattice_catalog SET workspace_id='another' WHERE id='system'",
    ],
)
def test_system_space_mutations_fail_without_losing_the_retained_root(database, statement):
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.execute(sa.text(statement))
    with database.connect() as connection:
        assert connection.execute(
            sa.text("SELECT system_key,installation_run_id,status FROM lattice_catalog WHERE id='system'")
        ).one() == ("organization", "run", "ready")


def test_system_label_changes_and_ordinary_folder_deletion_are_allowed(database):
    with database.begin() as connection:
        connection.execute(sa.text("UPDATE lattice_catalog SET name='Our organization' WHERE id='system'"))
        connection.execute(
            CatalogEntry.__table__.insert().values(
                id="user",
                tenant_id="org",
                kind="project",
                name="My folder",
                workspace_id="system",
                project_id="user",
                parent_id="system",
                created_by="user",
            )
        )
        connection.execute(sa.text("DELETE FROM lattice_catalog WHERE id='user'"))
        assert connection.execute(sa.text("SELECT name FROM lattice_catalog WHERE id='system'")).scalar() == (
            "Our organization"
        )
    if database.dialect.name == "sqlite":
        with database.connect() as connection:
            retained = connection.execute(
                sa.text("SELECT name,system_key FROM lattice_catalog WHERE id='retained'")
            ).first()
            if retained:
                assert retained == ("Retained user space", None)
