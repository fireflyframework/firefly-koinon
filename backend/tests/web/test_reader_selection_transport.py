# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Reader-aware detail requests preserve explicit local-only intent over HTTP."""

import asyncio

import pytest
from conftest import bearer

from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_context import current_reader_choices, reader_source_scope


@pytest.mark.asyncio
async def test_child_task_cannot_inherit_explicit_reader_choices():
    async def inherited_read():
        return current_reader_choices("actor", "tenant")

    with reader_source_scope("actor", "tenant", []):
        assert current_reader_choices("actor", "tenant") == ()
        with pytest.raises(SourceError):
            await asyncio.create_task(inherited_read())


@pytest.mark.asyncio
async def test_reader_scope_preserves_empty_choices_and_restores_parent():
    with reader_source_scope("actor", "tenant", []):
        assert current_reader_choices("actor", "tenant") == ()
    assert current_reader_choices("actor", "tenant") is None


def test_catalog_read_preserves_local_only_and_private_response(client):
    response = client.post(
        f"/api/v1/tenants/north/catalog/{client.workspace_id}/read",
        headers=bearer(),
        json={"reader_source_connections": []},
    )
    assert response.status_code == 200, response.text
    assert response.json()["name"] == "Research"
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["provenance", "coordinates", "availability"])
async def test_source_denial_precedes_native_or_availability_hydration(kind):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from koinon.knowledge.availability.dtos import AvailabilityRequest
    from koinon.knowledge.availability.service import KnowledgeAvailabilityService
    from koinon.knowledge.provenance.coordinate_service import TableCoordinateService
    from koinon.knowledge.provenance.service import TableProvenanceService

    reader = SimpleNamespace(begin=AsyncMock(side_effect=SourceError("access_denied")))
    knowledge = SimpleNamespace(source_reader=SimpleNamespace(get=lambda: reader))
    native = SimpleNamespace(read_snapshots=AsyncMock(), read_manifest=AsyncMock(), observe=AsyncMock())
    provenance = TableProvenanceService(knowledge, SimpleNamespace(get=lambda: native))
    provenance._bindings = AsyncMock(side_effect=AssertionError("bindings hydrated before source admission"))
    coordinates = TableCoordinateService(provenance, SimpleNamespace(get=lambda: native))
    availability = KnowledgeAvailabilityService(knowledge, SimpleNamespace(), native)
    availability._snapshot = AsyncMock(
        side_effect=AssertionError("availability hydrated before source admission")
    )
    with pytest.raises(SourceError):
        if kind == "provenance":
            await provenance.snapshot("actor", "tenant", "dataset", "table", str(uuid4()))
        elif kind == "coordinates":
            await coordinates.manifest("actor", "tenant", "dataset", "table", str(uuid4()))
        else:
            await availability.observe(
                "actor", "tenant", AvailabilityRequest(asset_ids=["document"], reader_source_connections=[])
            )
    assert not native.read_snapshots.called and not native.read_manifest.called and not native.observe.called


@pytest.mark.asyncio
async def test_download_source_guard_reconstructs_authority_in_stream_task():
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.integrations.content_sources.read_context import current_reader_snapshot
    from koinon.integrations.content_sources.read_dtos import ReaderSelectionSnapshot
    from koinon.knowledge.document_history.downloads import OriginalDownloads

    @asynccontextmanager
    async def fence():
        yield

    snapshot = ReaderSelectionSnapshot((), None)
    source = SimpleNamespace(selection=snapshot, used=set(), _entry_states={("doc",): ()})
    fresh = SimpleNamespace(used=set(), _entry_states={("doc",): ()}, release=AsyncMock(), read_fence=fence)
    observed = []

    async def entries(actor, tenant, identifiers, **options):
        observed.append((asyncio.current_task(), current_reader_snapshot(actor, tenant, None)))
        return fresh

    reader = SimpleNamespace(entries=entries)
    knowledge = SimpleNamespace(source_reader=SimpleNamespace(get=lambda: reader))
    downloads = OriginalDownloads(knowledge, None, None)
    guard = downloads._source_guard("actor", "tenant", "doc", None, source)
    await asyncio.create_task(guard())
    assert observed[0][0] is not asyncio.current_task()
    assert observed[0][1] == snapshot
    assert fresh.release.await_count == 1
    fresh._entry_states = {("doc",): ("changed",)}
    with pytest.raises(SourceError):
        await asyncio.create_task(guard())


@pytest.mark.parametrize(
    "selection",
    [
        [{"provider": "unknown", "connection_id": "reader"}],
        [
            {"provider": "google_drive", "connection_id": "one"},
            {"provider": "google_drive", "connection_id": "two"},
        ],
        [{"provider": "google_drive", "connection_id": "reader", "credential": "secret"}],
        [{"provider": "google_drive", "connection_id": "reader"}] * 101,
    ],
)
def test_catalog_read_rejects_invalid_choices_privately(client, selection):
    response = client.post(
        f"/api/v1/tenants/north/catalog/{client.workspace_id}/read",
        headers=bearer(),
        json={"reader_source_connections": selection},
    )
    assert response.status_code in (400, 422), response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "secret" not in response.text


def test_catalog_read_rejects_foreign_connection_without_local_fallback(client):
    response = client.post(
        f"/api/v1/tenants/north/catalog/{client.workspace_id}/read",
        headers=bearer(),
        json={"reader_source_connections": [{"provider": "google_drive", "connection_id": "foreign"}]},
    )
    assert response.status_code in (403, 404, 409), response.text
    assert response.headers["cache-control"] == "private, no-store"
    assert "Research" not in response.text


@pytest.mark.asyncio
async def test_history_filters_denied_identity_before_hydration_without_totals():
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from koinon.integrations.content_sources.read_dtos import ReaderSelectionSnapshot
    from koinon.knowledge.lineage.dtos import SnapshotIdentityPage
    from koinon.knowledge.provenance.read_dtos import SnapshotHistoryReadInput
    from koinon.knowledge.provenance.service import TableProvenanceService

    @asynccontextmanager
    async def fence():
        yield

    denied = str(uuid4())
    operation = SimpleNamespace(
        selection=ReaderSelectionSnapshot((), None), release=AsyncMock(), read_fence=fence
    )
    reader = SimpleNamespace(
        begin=AsyncMock(return_value=operation), entries=AsyncMock(side_effect=SourceError("access_denied"))
    )
    knowledge = SimpleNamespace(source_reader=SimpleNamespace(get=lambda: reader))
    native = SimpleNamespace(
        read_table_identities=AsyncMock(return_value=SnapshotIdentityPage((denied,), False, denied)),
        read_snapshots=AsyncMock(side_effect=AssertionError("Denied snapshot hydrated")),
    )
    service = TableProvenanceService(knowledge, SimpleNamespace(get=lambda: native))
    service._bindings = AsyncMock(
        return_value=(SimpleNamespace(native_workspace_id="w", native_id="d"), SimpleNamespace(native_id="t"))
    )
    result = await service.read_history(
        "actor", "tenant", "dataset", "table", SnapshotHistoryReadInput(reader_source_connections=[])
    )
    assert result.items == () and result.total is None and result.pages is None
    assert result.current_snapshot_id is None and result.next_cursor is None
    native.read_snapshots.assert_not_awaited()


@pytest.fixture(autouse=True)
def enable_reader_content_routes(monkeypatch):
    from koinon import app as application

    original = application.create_application

    def create(config, **options):
        config.setdefault("koinon", {})["knowledge"] = {"enabled": True}
        return original(config, **options)

    monkeypatch.setattr(application, "create_application", create)


def test_new_reader_routes_are_registered_and_private_json_errors(client):
    paths = {route.path for route in client.native_app.routes if "POST" in getattr(route, "methods", ())}
    prefix = "/api/v1/tenants/{tenant_id}/"
    expected = {
        "catalog/{entry_id}/read",
        "lineage/read",
        "datasets/{dataset_id}/schema/read",
        "documents/{document_id}/chunks/read",
        "documents/{document_id}/original/read",
        "documents/{document_id}/versions/read",
        "documents/{document_id}/versions/{source_version_id}/read",
        "documents/{document_id}/versions/{source_version_id}/extractions/read",
        "documents/{document_id}/versions/{source_version_id}/extractions/{extraction_id}/parts/read",
        "documents/{document_id}/versions/{source_version_id}/extractions/{extraction_id}/parts/{source_part_id}/read",
        "documents/{document_id}/versions/{source_version_id}/original/read",
        "knowledge-items/{item_id}/read",
        "knowledge-items/{item_id}/versions/{version}/read",
        "exports/{export_id}/read",
        "exports/{export_id}/download/read",
        "shares/{share_id}/read",
        "chat/threads/{thread_id}/read",
    }
    expected |= {
        "datasets/{dataset_id}/tables/{table_id}/" + suffix + "/read"
        for suffix in ("provenance", "snapshots", "coordinates", "coordinates/rows", "coordinates/columns")
    }
    assert {prefix + path for path in expected} <= paths
    response = client.post(
        f"/api/v1/tenants/north/catalog/{client.workspace_id}/read",
        headers={**bearer(), "Content-Type": "application/json"},
        content='{"secret":',
    )
    assert response.status_code in (400, 422)
    assert response.headers["cache-control"] == "private, no-store"
    assert "secret" not in response.text


def test_cookie_session_reader_post_requires_csrf(client):
    from conftest import ISSUER
    from pyfly.security.context import SecurityContext
    from pyfly.session import HttpSession
    from pyfly.session.ports.outbound import SessionStore

    store = client.native_app.state.context.get_bean(SessionStore)
    session = HttpSession("reader-csrf-test", is_new=True)
    session.set_attribute(
        "SECURITY_CONTEXT", SecurityContext(user_id="admin", attributes={"iss": ISSUER, "sub": "admin"})
    )
    client.portal.call(store.save, session.id, session.get_data(), 1800)
    client.cookies.set("PYFLY_SESSION", session.id, domain="testserver.local", path="/")
    denied = client.post(
        f"/api/v1/tenants/north/catalog/{client.workspace_id}/read", json={"reader_source_connections": []}
    )
    assert denied.status_code == 403
    assert denied.headers["cache-control"] == "private, no-store"
    assert denied.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_identity_chain_preserves_archive_denial_without_payload_reads():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.service import KnowledgeFacade

    catalog = SimpleNamespace(
        get_identity=AsyncMock(return_value=SimpleNamespace(id="document", status="archived")),
        get=AsyncMock(),
    )
    facade = object.__new__(KnowledgeFacade)
    facade.catalog = catalog
    with pytest.raises(AccessDenied):
        await facade._read_chain("reader", "tenant", "document", identities_only=True)
    catalog.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_history_local_version_positive_control_preserves_authorized_current_snapshot():
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from uuid import uuid4

    from koinon.integrations.content_sources.read_dtos import ReaderSelectionSnapshot
    from koinon.knowledge.lineage.dtos import SnapshotIdentityPage, SnapshotLineage
    from koinon.knowledge.provenance.read_dtos import SnapshotHistoryReadInput
    from koinon.knowledge.provenance.service import TableProvenanceService

    @asynccontextmanager
    async def fence():
        yield

    snapshot = str(uuid4())
    operation = SimpleNamespace(
        selection=ReaderSelectionSnapshot((), None), release=AsyncMock(), read_fence=fence
    )
    reader = SimpleNamespace(
        begin=AsyncMock(return_value=operation), entries=AsyncMock(return_value=operation)
    )
    native = SimpleNamespace(
        read_table_identities=AsyncMock(return_value=SnapshotIdentityPage((snapshot,), False, snapshot)),
        read_snapshots=AsyncMock(
            return_value=(SnapshotLineage("tenant", "w", snapshot, "d", "t", "not_recorded", "READY"),)
        ),
    )
    service = TableProvenanceService(
        SimpleNamespace(source_reader=SimpleNamespace(get=lambda: reader)),
        SimpleNamespace(get=lambda: native),
    )
    service._bindings = AsyncMock(
        return_value=(SimpleNamespace(native_workspace_id="w", native_id="d"), SimpleNamespace(native_id="t"))
    )
    value = await service.read_history(
        "reader", "tenant", "dataset", "table", SnapshotHistoryReadInput(reader_source_connections=[])
    )
    assert [item.snapshot_id for item in value.items] == [snapshot]
    assert value.current_snapshot_id == snapshot and value.total is None and value.pages is None


@pytest.mark.asyncio
async def test_stream_spool_closes_when_final_selection_check_fails(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from starlette.requests import Request

    from koinon.integrations.content_sources import read_requests
    from koinon.integrations.content_sources.read_dtos import ReaderReadInput, ReaderSelectionSnapshot
    from koinon.knowledge.document_history.download_response import OriginalFileResponse

    snapshot = ReaderSelectionSnapshot((), None)
    reader = SimpleNamespace(
        begin=AsyncMock(return_value=SimpleNamespace(selection=snapshot)),
        selections=SimpleNamespace(confirm=AsyncMock(side_effect=SourceError("authority_changed"))),
    )
    download = SimpleNamespace(
        receipt=SimpleNamespace(bytes=1, sha256="a" * 64, filename="doc"), close=AsyncMock()
    )
    response = OriginalFileResponse(download)
    monkeypatch.setattr(
        read_requests, "identity_from_request", lambda request: SimpleNamespace(subject="reader")
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/tenants/tenant/documents/doc/original/read",
            "headers": [],
            "query_string": b"",
        }
    )

    async def read(actor):
        return response

    result = await read_requests.reader_response(
        reader, request, "tenant", ReaderReadInput(reader_source_connections=[]), read
    )
    assert result.status_code == 409
    download.close.assert_awaited_once()


@pytest.fixture
def reader_postgres(record_property):
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "integrations/content_sources/test_source_migration_postgres.py"
    spec = importlib.util.spec_from_file_location("reader_transport_pg_fixture", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    yield from module.source_database.__wrapped__(record_property)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_native_history_identity_page_postgres(reader_postgres, monkeypatch):
    import importlib.util
    from contextlib import asynccontextmanager
    from pathlib import Path
    from types import SimpleNamespace
    from uuid import uuid4

    import psycopg
    from alembic import command
    from sqlalchemy import event
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.lineage import service as module

    target, _, engine = reader_postgres
    root = Path(__file__).parents[3]
    spec = importlib.util.spec_from_file_location("reader_transport_migrations", root / "deploy/migrate.py")
    migrate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrate)
    with engine.connect() as connection:
        command.upgrade(
            migrate.history_config(
                "structured", root / "packages/structured/migrations/versions", connection
            ),
            "head",
        )
        connection.commit()
    workspace, dataset, table, old, new, foreign = [uuid4() for _ in range(6)]
    with psycopg.connect(
        target.set(drivername="postgresql").render_as_string(hide_password=False)
    ) as connection:
        connection.execute(
            "INSERT INTO flyquery_workspaces(id,tenant_id,slug,name) VALUES(%s,'north','history','History')",
            (workspace,),
        )
        connection.execute(
            "INSERT INTO flyquery_datasets(id,tenant_id,workspace_id,name) VALUES(%s,'north',%s,'Dataset')",
            (dataset, workspace),
        )
        connection.execute(
            "INSERT INTO flyquery_tables(id,tenant_id,workspace_id,dataset_id,name,qualified_name) "
            "VALUES(%s,'north',%s,%s,'Table','dataset.Table')",
            (table, workspace, dataset),
        )
        for identifier, tenant, stamp in (
            (old, "north", "2026-01-01"),
            (new, "north", "2026-01-02"),
            (foreign, "foreign", "2026-01-03"),
        ):
            connection.execute(
                "INSERT INTO flyquery_schema_snapshots(id,tenant_id,workspace_id,dataset_id,table_id,"
                "taken_at,snapshot_hash,n_columns,status,triggered_by,created_by) "
                "VALUES(%s,%s,%s,%s,%s,%s,'protected-hash',1,'READY','USER','protected-actor')",
                (identifier, tenant, workspace, dataset, table, stamp),
            )
        connection.execute("UPDATE flyquery_tables SET current_snapshot_id=%s WHERE id=%s", (new, table))
    native = create_async_engine(target.set(drivername="postgresql+asyncpg"))
    sessions = async_sessionmaker(native, expire_on_commit=False)
    statements = []

    @event.listens_for(native.sync_engine, "before_cursor_execute")
    def observed(connection, cursor, statement, parameters, context, many):
        statements.append(statement)

    @asynccontextmanager
    async def unit(*args, **kwargs):
        async with sessions.begin() as session:
            yield session

    monkeypatch.setattr(module, "infrastructure_unit", unit)
    service = module.NativeStructuredLineage(SimpleNamespace(get=lambda name: None))
    scope = dict(
        actor="reader",
        tenant_id="north",
        workspace_id=str(workspace),
        dataset_id=str(dataset),
        table_id=str(table),
        page_size=1,
    )
    try:
        first = await service.read_table_identities(**scope)
        second = await service.read_table_identities(**scope, page=2)
        end = await service.read_table_identities(**scope, page=3)
        assert first.snapshot_ids == (str(new),) and first.scan_full
        assert second.snapshot_ids == (str(old),) and second.scan_full
        assert end.snapshot_ids == () and not end.scan_full
        assert first.current_snapshot_id == str(new)
        with pytest.raises(AccessDenied):
            await service.read_table_identities(**{**scope, "tenant_id": "foreign"})
        assert all(
            "snapshot_hash" not in statement
            and "created_by" not in statement
            and "count(" not in statement.lower()
            for statement in statements
        )
    finally:
        await native.dispose()
