# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Audit eligibility is retained across mutation and rechecked before egress."""

from types import SimpleNamespace

import psycopg
import pytest
from psycopg.types.json import Json
from test_catalog_audit_provenance_postgres import history_database as history_database
from test_folder_reader_postgres import folder, publication
from test_folder_reader_postgres import folder_application as folder_application
from test_folder_reader_postgres import retained_folder as retained_folder
from test_folder_reader_postgres import source_database as source_database
from test_folder_reader_postgres import source_sessions as source_sessions

from koinon.catalog.service import CatalogService

pytestmark = pytest.mark.integration


def audit(connection, identifier, resource, *, action="catalog.updated", details=None, tenant="retained"):
    connection.execute(
        "INSERT INTO lattice_audit(id,tenant_id,subject,action,resource_id,details,created_at) "
        "VALUES(%s,%s,'reader',%s,%s,%s,now())",
        (identifier, tenant, action, resource, Json(details or {"old_name": "Retained name"})),
    )


@pytest.mark.parametrize("retained_folder", [{"publish": False}], indirect=True)
@pytest.mark.parametrize("change", ["publication", "revocation", "unchanged"])
async def test_audit_controller_revalidates_after_actor_resolution(folder_application, monkeypatch, change):
    from pyfly.kernel import ServiceUnavailableException

    from koinon.api.controllers.audit import AuditController
    from koinon.catalog.errors import AccessDenied

    context, remote, uri = folder_application
    with psycopg.connect(uri) as connection:
        audit(connection, "candidate-event", "child")

    class Profiles:
        async def author_summaries(self, *args, **kwargs):
            with psycopg.connect(uri) as connection:
                if change == "publication":
                    folder(connection, "new-managed")
                    connection.execute("UPDATE lattice_catalog SET parent_id='new-managed' WHERE id='child'")
                    publication(connection, folder_id="new-managed")
                elif change == "revocation":
                    connection.execute("UPDATE lattice_memberships SET active=false WHERE id='reader'")
            return {"reader": {"display_name": "Reader"}}

    monkeypatch.setattr(
        "koinon.api.controllers.audit.identity_from_request", lambda _: SimpleNamespace(subject="reader")
    )
    controller = AuditController(context.get_bean(CatalogService), Profiles())
    if change == "unchanged":
        result = await controller.audit("retained", object(), action="catalog.updated")
        assert result["total"] == 1 and result["items"][0]["id"] == "candidate-event"
        assert result["actors"]["reader"]["display_name"] == "Reader"
    else:
        error = AccessDenied if change == "revocation" else ServiceUnavailableException
        with pytest.raises(error):
            await controller.audit("retained", object(), action="catalog.updated")
    assert not remote.calls


@pytest.mark.parametrize("transition", ["delete", "move_delete", "ancestor_move", "roundtrip"])
async def test_retained_history_survives_deletion_and_ancestry_changes(folder_application, transition):
    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        folder(connection, "ordinary")
        audit(connection, "local-history", "ordinary")
        resource = "child"
        if transition == "ancestor_move":
            folder(connection, "grandchild")
            connection.execute("UPDATE lattice_catalog SET parent_id='child' WHERE id='grandchild'")
            resource = "grandchild"
        audit(connection, "protected-history", resource)
        if transition != "delete":
            connection.execute("UPDATE lattice_catalog SET parent_id='folder' WHERE id='child'")
        if transition == "roundtrip":
            connection.execute("UPDATE lattice_catalog SET parent_id='managed' WHERE id='child'")
            connection.execute("UPDATE lattice_catalog SET parent_id='folder' WHERE id='child'")
        if transition in {"delete", "move_delete"}:
            connection.execute("DELETE FROM lattice_catalog WHERE id='child'")
        audit(
            connection,
            "forged-unknown",
            "deleted-before-capture",
            details={"coverage": "complete", "from_parent_id": "folder"},
        )
    service = context.get_bean(CatalogService)
    page = await service.audit_page("reader", "retained", action="catalog.updated")
    assert page["total"] == 1 and [row.id for row in page["items"]] == ["local-history"]
    assert [row.id for row in await service.audit("reader", "retained")] == ["local-history"]
    with psycopg.connect(uri) as connection:
        assert connection.execute(
            "SELECT count(*) FROM lattice_audit WHERE id='protected-history'"
        ).fetchone() == (1,)


async def test_retained_curated_dependencies_survive_replacement_and_removal(folder_application):
    from test_catalog_audit_provenance_postgres import curated_state, root

    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        for identifier in ("derived", "derived-again", "plain-source"):
            folder(connection, identifier)
        for identifier in ("derived", "derived-again"):
            curated_state(connection, identifier)
            audit(connection, identifier + "-event", identifier)
        root(connection, "derived-root", "derived", "child")
        root(connection, "second-root", "derived-again", "derived")
        connection.execute(
            "UPDATE koinon_curated_source_roots SET source_asset_id='plain-source' WHERE id='derived-root'"
        )
        connection.execute("DELETE FROM koinon_curated_source_roots")
        audit(connection, "plain-event", "plain-source")
    page = await context.get_bean(CatalogService).audit_page("reader", "retained", action="catalog.updated")
    assert page["total"] == 1 and [row.id for row in page["items"]] == ["plain-event"]


async def test_safe_operational_audit_never_crosses_tenant_boundary(folder_application):
    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        connection.execute("INSERT INTO lattice_tenants VALUES('other','Other',now())")
        connection.execute(
            "INSERT INTO lattice_memberships(id,subject,tenant_id,role,active,created_at) "
            "VALUES('foreign-member','foreign','other','admin',true,now())"
        )
        audit(connection, "local-control", "reader", action="membership.updated", details={"role": "viewer"})
        audit(
            connection,
            "foreign-control",
            "foreign-member",
            action="membership.updated",
            details={"role": "viewer"},
            tenant="other",
        )
    page = await context.get_bean(CatalogService).audit_page(
        "reader", "retained", action="membership.updated"
    )
    assert page["total"] == 1 and [row.id for row in page["items"]] == ["local-control"]


async def test_legacy_audit_authorization_and_projection_share_primary_snapshot(
    folder_application, monkeypatch
):
    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        audit(connection, "before-authorization", "folder")
    service = context.get_bean(CatalogService)
    authorize = service.authorize

    async def publish_after_authorization(*args, **kwargs):
        result = await authorize(*args, **kwargs)
        with psycopg.connect(uri) as connection:
            audit(connection, "after-authorization", "folder")
        return result

    monkeypatch.setattr(service, "authorize", publish_after_authorization)
    rows = await service.audit("reader", "retained")
    assert [row.id for row in rows] == ["before-authorization"]
    monkeypatch.setattr(service, "authorize", authorize)
    assert {row.id for row in await service.audit("reader", "retained")} == {
        "before-authorization",
        "after-authorization",
    }


async def test_legacy_unknown_history_is_withheld_without_disabling_new_local_children(history_database):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import create_async_engine
    from test_catalog_audit_provenance_postgres import catalog, curated_state, root

    from koinon.catalog.audit_history import eligible_events

    uri, _, _ = history_database
    with psycopg.connect(uri) as connection:
        catalog(connection, "new-child", "old-parent")
        audit(connection, "new-child-event", "new-child")
        for identifier, source in (("unknown-derived", "old-child"), ("local-derived", "new-child")):
            catalog(connection, identifier)
            curated_state(connection, identifier)
            root(connection, identifier + "-root", identifier, source)
            audit(connection, identifier + "-event", identifier)
        connection.execute("DELETE FROM koinon_curated_source_roots")
        connection.execute("DELETE FROM lattice_catalog WHERE id IN ('new-child','old-child')")
        connection.execute("DELETE FROM lattice_catalog WHERE id='old-parent'")
    engine = create_async_engine(uri.replace("postgresql://", "postgresql+asyncpg://"))
    try:
        async with engine.connect() as connection:
            rows = (await connection.execute(select(eligible_events("retained")))).mappings().all()
        assert {row["id"] for row in rows} == {"new-child-event", "local-derived-event"}
    finally:
        await engine.dispose()


async def test_audit_timeout_returns_controlled_unavailable_without_partial_counts(folder_application):
    import asyncio

    from pyfly.kernel import ServiceUnavailableException

    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        audit(connection, "local-history", "folder")
    service = context.get_bean(CatalogService)
    with psycopg.connect(uri) as blocker:
        blocker.execute("LOCK TABLE koinon_catalog_history_edges IN ACCESS EXCLUSIVE MODE")
        with pytest.raises(ServiceUnavailableException) as failure:
            await asyncio.wait_for(service.audit_page("reader", "retained", action="catalog.updated"), 5)
        assert failure.value.code == "AUDIT_UNAVAILABLE"
        blocker.rollback()
    page = await service.audit_page("reader", "retained", action="catalog.updated")
    assert page["total"] == 1 and [row.id for row in page["items"]] == ["local-history"]


async def test_actual_move_regression_detects_removed_retained_parent_edge(
    folder_application, record_property
):
    from test_folder_reader_postgres import (
        test_audit_history_stays_protected_after_authorized_move_to_local_parent,
    )

    await test_audit_history_stays_protected_after_authorized_move_to_local_parent(folder_application)
    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        assert connection.execute("SELECT current_database()").fetchone()[0].startswith("source_schema_")
        connection.execute(
            "ALTER TABLE koinon_catalog_history_edges DISABLE TRIGGER koinon_catalog_history_edges_rows"
        )
        removed = connection.execute(
            "DELETE FROM koinon_catalog_history_edges WHERE tenant_id='retained' "
            "AND dependent_id='child' AND origin_id='managed' AND kind='parent'"
        ).rowcount
        connection.execute(
            "ALTER TABLE koinon_catalog_history_edges ENABLE TRIGGER koinon_catalog_history_edges_rows"
        )
        assert removed == 1
    page = await context.get_bean(CatalogService).audit_page("reader", "retained", action="catalog.updated")
    with pytest.raises(AssertionError):
        assert page["total"] == 0 and not page["items"]
    assert [row.id for row in page["items"]] == ["protected-history"]
    record_property("detected_history_mutation", "retained_old_parent_edge")


async def test_full_audit_page_and_egress_queries_qualify_large_retained_graph(
    folder_application, monkeypatch, record_property
):
    import json
    from time import perf_counter

    from sqlalchemy import event, text
    from sqlalchemy.engine import Engine
    from sqlalchemy.ext.asyncio import create_async_engine
    from test_catalog_audit_provenance_postgres import populate_history_qualification

    from koinon.api.controllers.audit import AuditController

    context, _, uri = folder_application
    with psycopg.connect(uri) as connection:
        populate_history_qualification(connection)
        folder(connection, "ordinary")
        connection.execute("UPDATE lattice_catalog SET name='Local' WHERE id='ordinary'")
        audit(connection, "ordinary-event", "ordinary")
        counts = {
            table: connection.execute("SELECT count(*) FROM " + table).fetchone()[0]
            for table in (
                "koinon_catalog_history_identities",
                "koinon_catalog_history_edges",
                "lattice_audit",
            )
        }
    assert counts["koinon_catalog_history_identities"] >= 11000
    assert counts["koinon_catalog_history_edges"] >= 55000
    assert counts["lattice_audit"] >= 110000

    class Profiles:
        async def author_summaries(self, *args, **kwargs):
            return {}

    monkeypatch.setattr(
        "koinon.api.controllers.audit.identity_from_request", lambda _: SimpleNamespace(subject="reader")
    )
    controller = AuditController(context.get_bean(CatalogService), Profiles())
    statements, reports = [], []

    def capture(connection, cursor, statement, parameters, execution_context, executemany):
        if statement.lstrip().startswith("WITH RECURSIVE"):
            statements.append((statement, parameters))

    engine = create_async_engine(uri.replace("postgresql://", "postgresql+asyncpg://"))
    try:
        for protected, expected in ((False, 100001), (True, 1)):
            if protected:
                with psycopg.connect(uri) as connection:
                    connection.execute("UPDATE lattice_catalog SET parent_id='managed' WHERE id='q1'")
            statements.clear()
            event.listen(Engine, "before_cursor_execute", capture)
            started = perf_counter()
            try:
                result = await controller.audit(
                    "retained", object(), q="Local", action="catalog.updated", page_size=100
                )
            finally:
                event.remove(Engine, "before_cursor_execute", capture)
            elapsed = perf_counter() - started
            assert result["total"] == expected and len(result["items"]) == min(expected, 100)
            assert elapsed < 2, f"Complete audit request exceeded 2s: {elapsed:.3f}s"
            assert len(statements) == 4, (
                "Qualification must include count/page and the final identity-only recheck"
            )
            assert sum("eligible_audit.details" in statement for statement, _ in statements) == 1
            plans = []
            async with engine.connect() as connection:
                await connection.execute(text("SET LOCAL statement_timeout='2s'"))
                for statement, parameters in statements:
                    plan = (
                        await connection.exec_driver_sql(
                            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
                        )
                    ).scalar_one()[0]
                    assert plan["Execution Time"] < 2000
                    plans.append(plan)
            reports.append(
                {"protected": protected, "total": expected, "elapsed_seconds": elapsed, "plans": plans}
            )
    finally:
        await engine.dispose()
    record_property("audit_qualification_database", uri)
    record_property("audit_qualification_counts", json.dumps(counts))
    record_property("audit_qualification_queries", json.dumps(reports))
    import os
    from pathlib import Path

    if report_path := os.environ.get("KOINON_AUDIT_QUALIFICATION_REPORT"):
        Path(report_path).write_text(
            json.dumps({"database": uri, "counts": counts, "requests": reports}, indent=2)
        )
