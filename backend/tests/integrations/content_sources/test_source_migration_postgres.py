# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Upgrade real primary history without altering retained organizational data."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from sqlalchemy.engine import make_url

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[4]
TABLES = (
    "koinon_content_connections",
    "koinon_content_authorizations",
    "koinon_content_mappings",
    "koinon_content_objects",
    "koinon_content_imports",
    "koinon_content_publication_baselines",
    "koinon_content_publication_targets",
)


def load(filename):
    spec = importlib.util.spec_from_file_location(Path(filename).stem, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source_database(record_property):
    uri = os.environ.get("KOINON_CONTENT_SOURCES_TEST_PG_URL")
    if not uri:
        pytest.skip("Requires an explicitly owned content-source PostgreSQL fixture")
    base = make_url(uri)
    assert base.host == "127.0.0.1" and base.port not in (None, 18783)
    suffix = uuid4().hex[:12]
    database, role = "source_schema_" + suffix, "source_runtime_" + suffix
    with psycopg.connect(uri, autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8'").format(sql.Identifier(database))
        )
        admin.execute(
            sql.SQL("CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS").format(
                sql.Identifier(role)
            )
        )
    target = base.set(database=database)
    record_property("owned_database", database)
    record_property("owned_runtime_role", role)
    engine = sa.create_engine(target.set(drivername="postgresql+psycopg"))
    try:
        with engine.connect() as connection:
            config = load("deploy/migrate.py").history_config(
                "native", ROOT / "deploy/migrations/native_versions", connection
            )
            command.upgrade(config, "koinon_0044_knowledge_modes")
            connection.commit()
            connection.exec_driver_sql(
                "INSERT INTO lattice_tenants(id,name,created_at) VALUES('retained','Retained',now())"
            )
            connection.commit()
        yield target, role, engine
    finally:
        engine.dispose()
    # Retain the uniquely named synthetic database and role for independent review.


def upgrade_sources(engine):
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "head")
        connection.commit()


def test_source_migration_preserves_retained_rows_and_matches_entity_contracts(source_database):
    _, _, engine = source_database
    with engine.connect() as connection:
        before = connection.exec_driver_sql("SELECT to_jsonb(t) FROM lattice_tenants t").all()
    upgrade_sources(engine)
    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        assert set(TABLES) <= set(inspector.get_table_names())
        assert connection.exec_driver_sql("SELECT to_jsonb(t) FROM lattice_tenants t").all() == before
        assert connection.exec_driver_sql("SELECT version_num FROM koinon_native_version").scalar_one() == (
            "koinon_0059_structure_proofs"
        )
        from koinon.integrations.content_sources.entities import (
            PersonalSourceConnection,
            SourceAuthorizationChallenge,
        )
        from koinon.integrations.content_sources.import_entities import SourceImportAttempt
        from koinon.integrations.content_sources.mapping_entities import SourceMapping, SourceObject
        from koinon.integrations.content_sources.publication_entities import (
            SourcePublicationBaseline,
            SourcePublicationTarget,
            SourcePublicationTransaction,
        )

        for entity in (
            PersonalSourceConnection,
            SourceAuthorizationChallenge,
            SourceMapping,
            SourceObject,
            SourceImportAttempt,
            SourcePublicationBaseline,
            SourcePublicationTarget,
            SourcePublicationTransaction,
        ):
            actual = {column["name"]: column for column in inspector.get_columns(entity.__tablename__)}
            assert set(actual) == set(entity.__table__.columns.keys())
            for column in entity.__table__.columns:
                assert actual[column.name]["nullable"] == column.nullable
            actual_indexes = {index["name"] for index in inspector.get_indexes(entity.__tablename__)}
            assert {index.name for index in entity.__table__.indexes} <= actual_indexes
            expected_foreign = {tuple(fk.column_keys) for fk in entity.__table__.foreign_key_constraints}
            actual_foreign = {
                tuple(fk["constrained_columns"]) for fk in inspector.get_foreign_keys(entity.__tablename__)
            }
            assert expected_foreign <= actual_foreign
            expected_checks = {
                check.name for check in entity.__table__.constraints if isinstance(check, sa.CheckConstraint)
            }
            assert expected_checks <= {
                check["name"] for check in inspector.get_check_constraints(entity.__tablename__)
            }


def test_runtime_grants_keep_origin_bindings_and_receipts_protected(source_database):
    target, role, engine = source_database
    upgrade_sources(engine)
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    roles = load("deploy/provision_roles.py")
    with psycopg.connect(uri) as owner:
        owner.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
        for table in TABLES:
            roles.grant_table(owner, table, role)
    with psycopg.connect(uri) as owner:
        for table in TABLES:
            assert owner.execute(
                "SELECT has_table_privilege(%s,%s,'SELECT'),has_table_privilege(%s,%s,'INSERT'),"
                "has_table_privilege(%s,%s,'DELETE'),has_table_privilege(%s,%s,'TRUNCATE')",
                (role, table) * 4,
            ).fetchone() == (True, True, False, False)
        assert owner.execute(
            "SELECT has_column_privilege(%s,'koinon_content_imports','remote_version','UPDATE'),"
            "has_column_privilege(%s,'koinon_content_imports','receipt_json','UPDATE')",
            (role, role),
        ).fetchone() == (False, True)


def test_owner_inventory_uses_index_with_ten_thousand_connections(source_database):
    _, _, engine = source_database
    upgrade_sources(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("""
            INSERT INTO koinon_content_connections
                (id,tenant_id,owner,provider,status,revision,config_fingerprint,scopes,created_at,updated_at)
            SELECT 'connection-' || n, 'retained', 'person-' || n, 'google_drive',
                   'pending', 1, '', '[]'::json, now(), now()
            FROM generate_series(1,10000) AS n
        """)
        connection.exec_driver_sql("ANALYZE koinon_content_connections")
        plan = connection.exec_driver_sql("""
            EXPLAIN (ANALYZE, FORMAT JSON)
            SELECT id FROM koinon_content_connections
            WHERE tenant_id='retained' AND owner='person-9800'
        """).scalar_one()[0]["Plan"]
        assert plan["Actual Rows"] == 1
        assert plan["Node Type"] in {"Index Scan", "Bitmap Heap Scan", "Index Only Scan"}
        indexes = [plan, *plan.get("Plans", [])]
        assert any(node.get("Index Name") == "ix_content_connection_owner" for node in indexes)
