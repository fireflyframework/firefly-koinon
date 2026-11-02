# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Former bootstrap folders are ordinary content with retained installation provenance."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from psycopg import sql
from sqlalchemy.exc import IntegrityError

from koinon.catalog.entities import CatalogEntry, Tenant
from koinon.catalog.mappers import entry_dto


def load_migration(name):
    path = Path(__file__).resolve().parents[3] / "deploy/migrations/native_versions" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=[("sqlite", "runtime"), ("sqlite", "upgrade"), ("postgresql", "upgrade")])
def database(request):
    dialect, mode = request.param
    if dialect == "postgresql":
        uri = os.environ.get("KOINON_MEMORY_AUTHORITY_TEST_PG_URL")
        if not uri:
            pytest.skip("Requires an explicitly owned PostgreSQL fixture")
        url = sa.engine.make_url(uri)
        assert url.host == "127.0.0.1" and url.port != 18783
        name = "ordinary_folders_" + uuid4().hex[:12]
        with psycopg.connect(uri, autocommit=True) as owner:
            owner.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        engine = sa.create_engine(
            url.set(drivername="postgresql+psycopg", database=name), hide_parameters=True
        )
    else:
        engine = sa.create_engine("sqlite://", hide_parameters=True)
    with engine.begin() as connection:
        Tenant.__table__.create(connection)
        connection.execute(Tenant.__table__.insert().values(id="org", name="Organization"))
        CatalogEntry.__table__.create(connection)
        connection.execute(
            CatalogEntry.__table__.insert().values(
                id="space",
                tenant_id="org",
                workspace_id="space",
                kind="workspace",
                name="Our space",
                created_by="system:installation",
                system_key="original-space",
                installation_run_id="retained-run",
                metadata_json={"tags": ["retained"]},
            )
        )
        for identifier in ("one", "two"):
            connection.execute(
                CatalogEntry.__table__.insert().values(
                    id=identifier,
                    tenant_id="org",
                    workspace_id="space",
                    project_id=identifier,
                    parent_id="space",
                    kind="project",
                    name=identifier,
                    created_by="person",
                )
            )
        connection.execute(
            CatalogEntry.__table__.insert().values(
                id="folder",
                tenant_id="org",
                workspace_id="space",
                project_id="one",
                parent_id="one",
                kind="collection",
                name="Retained documents",
                created_by="system:installation",
                system_key="original-folder",
                installation_run_id="retained-run",
            )
        )
        if mode == "upgrade":
            if dialect == "sqlite":
                connection.exec_driver_sql("DROP TRIGGER koinon_system_space_update")
                connection.exec_driver_sql("DROP TRIGGER IF EXISTS koinon_system_space_delete")
            else:
                connection.exec_driver_sql("DROP TRIGGER koinon_system_space_rows ON public.lattice_catalog")
                connection.exec_driver_sql(
                    "DROP TRIGGER koinon_system_space_truncate ON public.lattice_catalog"
                )
                connection.exec_driver_sql("DROP FUNCTION public.koinon_system_space_guard()")
            for statement in load_migration("0037_system_spaces.py").system_space_guards(dialect):
                connection.exec_driver_sql(statement)
            before = connection.execute(sa.select(CatalogEntry.__table__)).all()
            with Operations.context(MigrationContext.configure(connection)):
                load_migration("0043_ordinary_installation_folders.py").upgrade()
            assert connection.execute(sa.select(CatalogEntry.__table__)).all() == before
    try:
        yield engine
    finally:
        engine.dispose()


def test_former_defaults_can_be_archived_moved_and_deleted(database):
    with database.begin() as connection:
        connection.exec_driver_sql("UPDATE lattice_catalog SET status='archived' WHERE id='space'")
        connection.exec_driver_sql(
            "UPDATE lattice_catalog SET parent_id='two',project_id='two' WHERE id='folder'"
        )
        assert connection.execute(
            sa.text(
                "SELECT parent_id,project_id,system_key,installation_run_id "
                "FROM lattice_catalog WHERE id='folder'"
            )
        ).one() == ("two", "two", "original-folder", "retained-run")
        connection.exec_driver_sql("DELETE FROM lattice_catalog WHERE id='folder'")
        assert (
            connection.execute(sa.text("SELECT count(*) FROM lattice_catalog WHERE id='folder'")).scalar()
            == 0
        )


@pytest.mark.parametrize("column", ["system_key", "installation_run_id"])
def test_installation_provenance_remains_immutable(database, column):
    with pytest.raises(IntegrityError), database.begin() as connection:
        connection.exec_driver_sql(f"UPDATE lattice_catalog SET {column}=NULL WHERE id='folder'")


def test_public_folder_has_no_system_protection(database):
    from sqlalchemy.orm import Session

    with Session(database) as session:
        folder = session.get(CatalogEntry, "folder")
        assert entry_dto(folder)["system_managed"] is False
        assert folder.created_by == "system:installation"
        assert folder.installation_run_id == "retained-run"
