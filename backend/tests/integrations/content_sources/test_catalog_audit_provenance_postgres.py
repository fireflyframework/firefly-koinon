# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Retained typed history survives ordinary catalog mutations on real PostgreSQL."""

import psycopg
import pytest
import sqlalchemy as sa
from alembic import command
from psycopg import sql
from test_source_migration_postgres import ROOT, load, upgrade_sources
from test_source_migration_postgres import source_database as source_database

pytestmark = pytest.mark.integration
IDENTITIES = "koinon_catalog_history_identities"
EDGES = "koinon_catalog_history_edges"


def catalog(connection, identifier, parent=None, tenant="retained"):
    connection.execute(
        "INSERT INTO lattice_catalog "
        "(id,tenant_id,parent_id,kind,name,description,status,metadata_json,created_by,updated_by,"
        "created_at,updated_at) VALUES(%s,%s,%s,'folder',%s,'','ready','{}','actor','actor',now(),now())",
        (identifier, tenant, parent, identifier),
    )


def audit(connection, identifier, resource):
    connection.execute(
        "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
        "VALUES(%s,'retained','actor','catalog.created',%s,'{}',now())",
        (identifier, resource),
    )


def curated_state(connection, item):
    connection.execute(
        "INSERT INTO koinon_curated_catalog_state "
        "(item_id,tenant_id,workspace_id,native_item_id,native_workspace_id,head_version,"
        "head_version_id,head_operation_id,root_count) "
        "VALUES(%s,'retained','workspace',%s,'native-workspace',1,'version','operation',1)",
        (item, item),
    )


def root(connection, identifier, item, origin, version="v1"):
    connection.execute(
        "INSERT INTO koinon_curated_source_roots "
        "(id,tenant_id,item_id,native_version_id,source_asset_id) VALUES(%s,'retained',%s,%s,%s)",
        (identifier, item, version, origin),
    )


@pytest.fixture
def history_database(source_database):
    target, role, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0050_reader_selection")
        connection.commit()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        catalog(connection, "old-parent")
        catalog(connection, "old-child", "old-parent")
        audit(connection, "old-event", "old-child")
        audit(connection, "unseen-event", "deleted-before-cutover")
    upgrade_sources(engine)
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT to_regclass(%s)", (IDENTITIES,)).fetchone()[0] == IDENTITIES
    return uri, role, engine


def test_upgrade_preserves_unknown_and_captures_new_local_moves_and_deletion(history_database):
    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            f"SELECT resource_id,coverage FROM {IDENTITIES} ORDER BY resource_id"
        ).fetchall() == [("old-child", "legacy_unknown"), ("old-parent", "legacy_unknown")]
        catalog(connection, "new-parent")
        catalog(connection, "new-child", "old-parent")
        audit(connection, "new-event", "new-child")
        connection.execute("UPDATE lattice_catalog SET parent_id='new-parent' WHERE id='new-child'")
        connection.execute("UPDATE lattice_catalog SET parent_id='old-parent' WHERE id='new-child'")
        connection.execute("DELETE FROM lattice_catalog WHERE id='new-child'")
        assert connection.execute(
            f"SELECT origin_id,kind FROM {EDGES} WHERE dependent_id='new-child' ORDER BY origin_id"
        ).fetchall() == [("new-parent", "parent"), ("old-parent", "parent")]
        assert connection.execute(
            f"SELECT coverage FROM {IDENTITIES} WHERE resource_id='new-child'"
        ).fetchone() == ("complete",)
        assert connection.execute("SELECT count(*) FROM lattice_audit").fetchone() == (3,)
        assert connection.execute(
            f"SELECT count(*) FROM {IDENTITIES} WHERE resource_id='deleted-before-cutover'"
        ).fetchone() == (0,)
        with pytest.raises(psycopg.errors.UniqueViolation), connection.transaction():
            catalog(connection, "new-child")


@pytest.mark.parametrize("tenant", ["retained", "other"])
def test_unknown_deleted_audit_identity_cannot_be_recreated_as_complete(history_database, tenant):
    uri, role, _ = history_database
    with psycopg.connect(uri) as connection:
        connection.execute("INSERT INTO lattice_tenants VALUES('other','Other',now())")
        for table in ("lattice_catalog", "lattice_audit", IDENTITIES):
            load("deploy/provision_roles.py").grant_table(connection, table, role)
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            catalog(connection, "deleted-before-cutover", tenant=tenant)
        assert connection.execute(
            f"SELECT count(*) FROM {IDENTITIES} WHERE resource_id='deleted-before-cutover'"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT resource_id FROM lattice_audit WHERE id='unseen-event'"
        ).fetchone() == ("deleted-before-cutover",)
        catalog(connection, "ordinary-new-local", tenant=tenant)
        assert connection.execute(
            f"SELECT coverage FROM {IDENTITIES} WHERE resource_id='ordinary-new-local'"
        ).fetchone() == ("complete",)


def test_capture_rejects_reassignment_and_cross_tenant_edges_atomically(history_database):
    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        connection.execute("INSERT INTO lattice_tenants VALUES('other','Other',now())")
        catalog(connection, "foreign", tenant="other")
        catalog(connection, "local")
        for statement in (
            "UPDATE lattice_catalog SET tenant_id='other' WHERE id='local'",
            "UPDATE lattice_catalog SET id='replacement' WHERE id='local'",
            "UPDATE lattice_catalog SET parent_id='foreign' WHERE id='local'",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            catalog(connection, "bad-child", "foreign")
        assert (
            connection.execute(
                f"SELECT resource_id FROM {IDENTITIES} WHERE resource_id IN ('bad-child','replacement')"
            ).fetchall()
            == []
        )
        assert connection.execute(
            "SELECT tenant_id,parent_id FROM lattice_catalog WHERE id='local'"
        ).fetchone() == ("retained", None)


def test_curated_replacement_retains_all_versions_and_deleted_associations(history_database):
    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        for identifier in ("derived", "source-a", "source-b", "source-c"):
            catalog(connection, identifier)
        curated_state(connection, "derived")
        root(connection, "lineage-a", "derived", "source-a")
        root(connection, "lineage-b", "derived", "source-b", "v2")
        connection.execute(
            "UPDATE koinon_curated_source_roots SET source_asset_id='source-c' WHERE id='lineage-b'"
        )
        connection.execute("DELETE FROM koinon_curated_source_roots")
        connection.execute("DELETE FROM koinon_curated_catalog_state")
        connection.execute("DELETE FROM lattice_catalog WHERE id='derived'")
        assert connection.execute(
            f"SELECT origin_id,kind FROM {EDGES} WHERE dependent_id='derived' ORDER BY origin_id"
        ).fetchall() == [(name, "curated_source") for name in ("source-a", "source-b", "source-c")]


def test_runtime_grants_and_guards_block_rewriting_even_with_column_grants(history_database):
    uri, role, _ = history_database
    roles = load("deploy/provision_roles.py")
    with psycopg.connect(uri) as owner:
        catalog(owner, "local")
        audit(owner, "event", "local")
        for table in (IDENTITIES, EDGES, "lattice_audit", "lattice_catalog"):
            roles.grant_table(owner, table, role)
        assert owner.execute(
            "SELECT has_table_privilege(%s,%s,'SELECT'),has_table_privilege(%s,%s,'INSERT')",
            (role, IDENTITIES, role, IDENTITIES),
        ).fetchone() == (True, False)
        owner.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        catalog(owner, "runtime-child", "local")
        audit(owner, "runtime-event", "runtime-child")
        for statement in (
            f"INSERT INTO {IDENTITIES} VALUES('retained','forged','complete')",
            f"UPDATE {IDENTITIES} SET coverage='complete' WHERE resource_id='old-child'",
            f"DELETE FROM {EDGES}",
            f"TRUNCATE {IDENTITIES} CASCADE",
            "UPDATE lattice_audit SET details='{}'",
            "DELETE FROM lattice_audit",
            "TRUNCATE lattice_audit",
        ):
            with pytest.raises(psycopg.errors.InsufficientPrivilege), owner.transaction():
                owner.execute(statement)
        owner.execute("RESET ROLE")
        for table, column in ((IDENTITIES, "coverage"), ("lattice_audit", "details")):
            owner.execute(
                sql.SQL("GRANT UPDATE ({}) ON {} TO {}").format(
                    sql.Identifier(column), sql.Identifier(table), sql.Identifier(role)
                )
            )
        owner.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        for statement in (
            f"UPDATE {IDENTITIES} SET coverage='complete' WHERE resource_id='old-child'",
            "UPDATE lattice_audit SET details='{}'",
        ):
            with pytest.raises(psycopg.errors.CheckViolation), owner.transaction():
                owner.execute(statement)
        owner.execute("RESET ROLE")
        for table in (IDENTITIES, "lattice_audit"):
            roles.grant_table(owner, table, role)
        assert owner.execute(
            "SELECT has_column_privilege(%s,%s,'coverage','UPDATE')", (role, IDENTITIES)
        ).fetchone() == (False,)


def test_failed_transaction_leaves_no_capture_or_audit_fragment(history_database):
    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        with pytest.raises(psycopg.errors.DivisionByZero), connection.transaction():
            catalog(connection, "aborted", "old-parent")
            audit(connection, "aborted-event", "aborted")
            connection.execute("SELECT 1/0")
        assert connection.execute(
            f"SELECT count(*) FROM {IDENTITIES} WHERE resource_id='aborted'"
        ).fetchone() == (0,)
        assert connection.execute(
            f"SELECT count(*) FROM {EDGES} WHERE dependent_id='aborted'"
        ).fetchone() == (0,)
        assert connection.execute(
            "SELECT count(*) FROM lattice_audit WHERE id='aborted-event'"
        ).fetchone() == (0,)


def test_append_only_guards_resist_accidental_broad_runtime_grants(history_database):
    uri, role, _ = history_database
    with psycopg.connect(uri) as connection:
        for table in (IDENTITIES, EDGES, "lattice_audit"):
            connection.execute(
                sql.SQL("GRANT ALL ON {} TO {}").format(sql.Identifier(table), sql.Identifier(role))
            )
        connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
        statements = (
            f"INSERT INTO {IDENTITIES} VALUES('retained','forged','complete')",
            f"INSERT INTO {EDGES} VALUES('retained','old-parent','old-child','parent')",
            f"UPDATE {IDENTITIES} SET coverage='complete' WHERE resource_id='old-child'",
            f"UPDATE {EDGES} SET kind='curated_source'",
            f"DELETE FROM {IDENTITIES}",
            f"DELETE FROM {EDGES}",
            f"TRUNCATE {IDENTITIES} CASCADE",
            f"TRUNCATE {EDGES}",
            "UPDATE lattice_audit SET details='{}'",
            "DELETE FROM lattice_audit",
            "TRUNCATE lattice_audit",
        )
        for statement in statements:
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute(statement)
        assert connection.execute(
            "SELECT has_function_privilege(current_user,'public.koinon_history_catalog_capture()','EXECUTE'),"
            "has_function_privilege(current_user,'public.koinon_history_curated_capture()','EXECUTE')"
        ).fetchone() == (False, False)
        assert connection.execute(f"SELECT count(*) FROM {EDGES}").fetchone() == (1,)


def test_curated_cross_tenant_association_aborts_without_a_retained_edge(history_database):
    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        catalog(connection, "derived")
        curated_state(connection, "derived")
        connection.execute("INSERT INTO lattice_tenants VALUES('other','Other',now())")
        catalog(connection, "foreign-source", tenant="other")
        with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
            root(connection, "bad-root", "derived", "foreign-source")
        assert connection.execute(
            f"SELECT count(*) FROM {EDGES} WHERE dependent_id='derived'"
        ).fetchone() == (0,)
        assert connection.execute("SELECT count(*) FROM koinon_curated_source_roots").fetchone() == (0,)


def test_fresh_install_and_metadata_match_without_inventing_legacy_coverage(source_database):
    from pyfly.data.relational.sqlalchemy import Base

    from koinon.catalog.entities import AuditEvent, CatalogEntry, Tenant
    from koinon.catalog.history_entities import CatalogHistoryEdge, CatalogHistoryIdentity
    from koinon.knowledge.curated.entities import CuratedCatalogState, CuratedSourceRoot

    target, _, engine = source_database
    upgrade_sources(engine)
    with engine.connect() as connection:
        inspector = sa.inspect(connection)
        for entity in (CatalogHistoryIdentity, CatalogHistoryEdge):
            actual = {column["name"]: column for column in inspector.get_columns(entity.__tablename__)}
            assert set(actual) == set(entity.__table__.columns.keys())
            assert all(
                actual[column.name]["nullable"] == column.nullable for column in entity.__table__.columns
            )
            assert {index.name for index in entity.__table__.indexes} <= {
                index["name"] for index in inspector.get_indexes(entity.__tablename__)
            }
        assert connection.exec_driver_sql(f"SELECT count(*) FROM {IDENTITIES}").scalar_one() == 0
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        catalog(connection, "fresh")
        assert connection.execute(f"SELECT coverage FROM {IDENTITIES}").fetchall() == [("complete",)]
    # A separate fresh schema exercises the direct Base.metadata entry point.
    # Use its own database; never remove the migrated fixture's guards or tables.
    from uuid import uuid4

    database = "history_metadata_" + uuid4().hex[:12]
    with psycopg.connect(uri, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(database)))
    metadata_engine = sa.create_engine(target.set(database=database, drivername="postgresql+psycopg"))
    try:
        with metadata_engine.begin() as connection:
            Base.metadata.create_all(
                connection,
                tables=[
                    entity.__table__
                    for entity in (
                        Tenant,
                        CatalogEntry,
                        AuditEvent,
                        CatalogHistoryIdentity,
                        CatalogHistoryEdge,
                        CuratedCatalogState,
                        CuratedSourceRoot,
                    )
                ],
            )
            connection.exec_driver_sql("INSERT INTO lattice_tenants VALUES('retained','Retained',now())")
        with psycopg.connect(
            target.set(database=database, drivername="postgresql").render_as_string(hide_password=False)
        ) as connection:
            catalog(connection, "metadata-local")
            audit(connection, "metadata-event", "metadata-local")
            assert connection.execute(f"SELECT coverage FROM {IDENTITIES}").fetchall() == [("complete",)]
            with pytest.raises(psycopg.errors.CheckViolation), connection.transaction():
                connection.execute("DELETE FROM lattice_audit")
    finally:
        metadata_engine.dispose()


def test_cutover_retains_typed_curated_versions_without_inventing_json_dependencies(source_database):
    target, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0050_reader_selection")
        connection.commit()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        for identifier in ("derived", "source-a", "source-b"):
            catalog(connection, identifier)
        curated_state(connection, "derived")
        root(connection, "old-v1", "derived", "source-a", "v1")
        root(connection, "old-v2", "derived", "source-b", "v2")
        audit(connection, "forged-event", "derived")
        connection.execute(
            'UPDATE lattice_audit SET details=\'{"from_parent_id":"invented-origin","coverage":"complete"}\''
        )
    upgrade_sources(engine)
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            f"SELECT dependent_id,origin_id,kind FROM {EDGES} ORDER BY origin_id"
        ).fetchall() == [("derived", name, "curated_source") for name in ("source-a", "source-b")]
        assert (
            connection.execute(f"SELECT coverage FROM {IDENTITIES}").fetchall() == [("legacy_unknown",)] * 3
        )
        assert connection.execute("SELECT details FROM lattice_audit").fetchone()[0] == {
            "from_parent_id": "invented-origin",
            "coverage": "complete",
        }
        assert connection.execute(
            f"SELECT count(*) FROM {IDENTITIES} WHERE resource_id='invented-origin'"
        ).fetchone() == (0,)


def test_malformed_cutover_rolls_back_and_excludes_concurrent_writers(source_database):
    target, _, engine = source_database
    with engine.connect() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "koinon_0050_reader_selection")
        connection.commit()
    uri = target.set(drivername="postgresql").render_as_string(hide_password=False)
    with psycopg.connect(uri) as connection:
        connection.execute("INSERT INTO lattice_tenants VALUES('other','Other',now())")
        catalog(connection, "foreign", tenant="other")
        catalog(connection, "malformed", "foreign")
        audit(connection, "retained-event", "malformed")
    with pytest.raises(sa.exc.IntegrityError, match="uq_catalog_history_resource"):
        upgrade_sources(engine)
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT version_num FROM koinon_native_version").fetchone() == (
            "koinon_0050_reader_selection",
        )
        assert connection.execute("SELECT to_regclass(%s)", (IDENTITIES,)).fetchone() == (None,)
        assert connection.execute("SELECT count(*) FROM lattice_audit").fetchone() == (1,)
        connection.execute("UPDATE lattice_catalog SET parent_id=NULL WHERE id='malformed'")
    with engine.begin() as connection:
        config = load("deploy/migrate.py").history_config(
            "native", ROOT / "deploy/migrations/native_versions", connection
        )
        command.upgrade(config, "head")
        with psycopg.connect(uri) as writer:
            writer.execute("SET LOCAL lock_timeout='100ms'")
            with pytest.raises(psycopg.errors.LockNotAvailable), writer.transaction():
                writer.execute("UPDATE lattice_catalog SET name='concurrent' WHERE id='malformed'")
    with psycopg.connect(uri) as connection:
        assert connection.execute(f"SELECT DISTINCT coverage FROM {IDENTITIES}").fetchall() == [
            ("legacy_unknown",)
        ]


def populate_history_qualification(connection):
    """Production-shaped retained graph built exclusively through captured writes.

    Return a reusable fixture for reader/Performance qualification: 11,040
    identities, over 55,000 deduplicated edges, 110,000 audit rows, two tenants,
    branching/diamonds/repeated moves, a cycle and a forty-edge historical chain.
    """
    for tenant, prefix, count in (("retained", "q", 10000), ("qualification-other", "z", 1000)):
        if tenant != "retained":
            connection.execute("INSERT INTO lattice_tenants VALUES(%s,'Other',now())", (tenant,))
        connection.execute(
            "INSERT INTO lattice_catalog(id,tenant_id,kind,name,description,status,metadata_json,"
            "created_by,updated_by,created_at,updated_at) "
            "SELECT %s||n,%s,'folder','Local','','ready','{}','actor','actor',now(),now() "
            "FROM generate_series(1,%s) n",
            (prefix, tenant, count),
        )
        for offset in range(1, 6):
            connection.execute(
                "UPDATE lattice_catalog SET parent_id=%s||(((substring(id FROM 2)::integer-1)/10)+%s) "
                "WHERE tenant_id=%s AND id LIKE %s",
                (prefix, offset, tenant, prefix + "%"),
            )
        # Repeat an already captured move; the unique edge key must bound storage.
        connection.execute(
            "UPDATE lattice_catalog SET parent_id=%s||(((substring(id FROM 2)::integer-1)/10)+1) "
            "WHERE tenant_id=%s AND id LIKE %s",
            (prefix, tenant, prefix + "%"),
        )
        connection.execute(
            "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
            "SELECT %s||'event-'||n,%s,'actor','catalog.updated',%s||((n-1)%%%s+1),'{}',now() "
            "FROM generate_series(1,%s) n",
            (prefix, tenant, prefix, count, count * 10),
        )
    for n in range(40):
        catalog(connection, "deep-" + str(n), "q1" if n == 0 else "deep-" + str(n - 1))
    for table in (IDENTITIES, EDGES, "lattice_audit"):
        connection.execute(sql.SQL("ANALYZE {}").format(sql.Identifier(table)))


def plan_nodes(plan):
    yield plan
    for child in plan.get("Plans", []):
        yield from plan_nodes(child)


def test_history_graph_qualification_uses_bounded_indexed_identity_recursion(
    history_database, record_property
):
    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        populate_history_qualification(connection)
        assert connection.execute(f"SELECT count(*) FROM {EDGES}").fetchone()[0] == 55041
        assert connection.execute("SELECT count(*) FROM lattice_audit").fetchone()[0] == 110002
        connection.execute("SET LOCAL statement_timeout='2s'")
        report = connection.execute(f"""
            EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)
            WITH RECURSIVE protected(tenant_id,resource_id) AS (
              SELECT tenant_id,resource_id FROM {IDENTITIES} WHERE tenant_id='retained' AND resource_id='q1'
              UNION
              SELECT e.tenant_id,e.dependent_id FROM {EDGES} e
              JOIN protected p ON e.tenant_id=p.tenant_id AND e.origin_id=p.resource_id
            ) SELECT count(*) FROM protected
        """).fetchone()[0][0]
        assert report["Execution Time"] < 2000
        nodes = list(plan_nodes(report["Plan"]))
        assert any(node.get("Index Name") == "ix_catalog_history_origin" for node in nodes)
        assert not any(
            node["Node Type"] == "Seq Scan" and node.get("Relation Name") == EDGES for node in nodes
        )
        assert next(node for node in nodes if node["Node Type"] == "Recursive Union")["Actual Rows"] == 10040
        record_property("history_graph_plan", report)
        record_property("history_graph_uri", uri)
        lookup = connection.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT 1 FROM lattice_audit WHERE resource_id='q9999'"
        ).fetchone()[0][0]
        assert any(
            node.get("Index Name") == "ix_catalog_audit_resource" for node in plan_nodes(lookup["Plan"])
        )
        record_property("history_identity_reuse_plan", lookup)


@pytest.mark.parametrize(
    "mutation", ["parent_capture", "legacy_coverage", "tenant_identity", "audit_immutable"]
)
def test_history_behavior_detects_removed_database_guard(history_database, mutation, record_property):
    """Causal checks change only this test's uniquely owned synthetic database."""
    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0].startswith("source_schema_")
        if mutation == "parent_capture":
            connection.execute("DROP TRIGGER koinon_history_catalog_capture ON lattice_catalog")
        elif mutation == "legacy_coverage":
            connection.execute(f"ALTER TABLE {IDENTITIES} DISABLE TRIGGER {IDENTITIES}_rows")
            connection.execute(f"UPDATE {IDENTITIES} SET coverage='complete'")
            connection.execute(f"ALTER TABLE {IDENTITIES} ENABLE TRIGGER {IDENTITIES}_rows")
        elif mutation == "tenant_identity":
            definition = connection.execute(
                "SELECT pg_get_functiondef('public.koinon_history_catalog_identity()'::regprocedure)"
            ).fetchone()[0]
            before = (
                "ELSIF NEW.id IS DISTINCT FROM OLD.id OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN"
            )
            assert before in definition
            connection.execute(definition.replace(before, "ELSIF false THEN"))
        else:
            connection.execute("DROP TRIGGER koinon_history_audit_rows ON lattice_audit")
    if mutation in {"parent_capture", "legacy_coverage"}:
        with pytest.raises(AssertionError):
            test_upgrade_preserves_unknown_and_captures_new_local_moves_and_deletion(history_database)
    elif mutation == "tenant_identity":
        with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
            test_capture_rejects_reassignment_and_cross_tenant_edges_atomically(history_database)
    else:
        with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"):
            test_runtime_grants_and_guards_block_rewriting_even_with_column_grants(history_database)
    record_property("detected_history_mutation", mutation)
