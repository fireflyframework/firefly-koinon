# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Mounted compatibility reads must not bypass immutable imported-source authority."""

from types import SimpleNamespace

import httpx
import psycopg
import pytest
from flycanon.core.services.sources.get_source_handler import GetSourceHandler
from flycanon.models.entities.source import SourceRow
from flycanon.models.repositories import SourceRepository
from flycanon.web.controllers.sources_controller import SourcesController
from pyfly.context import ApplicationContext
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.security.context import SecurityContext
from sqlalchemy import text
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from test_read_origins_postgres import PIN, commit_origin
from test_read_origins_postgres import retained_origin as retained_origin
from test_source_concurrency_postgres import source_sessions as source_sessions
from test_source_migration_postgres import source_database as source_database

from koinon.catalog.entities import CatalogEntry, Membership
from koinon.catalog.repositories import CatalogRepository, MembershipRepository, TenantRepository
from koinon.catalog.service import CatalogService
from koinon.integrations.content_sources.errors import SourceError
from koinon.integrations.content_sources.read_authority import SourceReadAuthority
from koinon.integrations.content_sources.read_repository import SourceReadRepository
from koinon.integrations.content_sources.read_service import SourceReader
from koinon.integrations.content_sources.reader_selection_repository import SourceReaderSelectionRepository
from koinon.integrations.content_sources.reader_selection_service import SourceReaderSelections
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.legacy_read import LegacyReadAdmission
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings
from koinon.web.legacy_security import LegacyMembershipFilter, LegacyOperationPolicies
from koinon.web.projection import _projected

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("imported", [False, True])
async def test_imported_legacy_source_read_checks_origin_before_native_hydration(
    retained_origin, source_database, imported
):
    sessions, uri = retained_origin
    target, _, engine = source_database
    commit_origin(uri)
    with psycopg.connect(uri) as connection:
        connection.execute(
            "UPDATE koinon_content_connections SET status='disconnected',revision=revision+1,"
            "secret_ciphertext=NULL"
            " WHERE id='connection'"
        )
    # This is a retained imported marker and exact receipt, not a fake source tag.
    async with sessions() as session:
        with pytest.raises(SourceError, match="unavailable"):
            await SourceReadRepository(session=session).resolve("retained", (PIN,))
    SourceRow.__table__.create(engine, checkfirst=True)
    url = target.set(drivername="postgresql+asyncpg").render_as_string(hide_password=False)
    context = ApplicationContext(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "enabled": True,
                            "ddl-auto": "none",
                            "url": url,
                            "datasources": {"canon": {"url": url, "ddl-auto": "none"}},
                        }
                    }
                }
            }
        )
    )
    await context.start()
    try:
        registry = context.get_bean(DataSourceRegistry)
        async with infrastructure_unit(registry.primary) as session:
            await session.execute(text("UPDATE lattice_catalog SET kind='collection' WHERE id='folder'"))
            session.add(Membership(id="reader", subject="issuer|alice", tenant_id="retained", role="viewer"))
            session.add(
                DomainBinding(
                    id="workspace-binding",
                    tenant_id="retained",
                    catalog_id="workspace",
                    workspace_id="workspace",
                    domain="canon",
                    entity_kind="workspace",
                    native_id="native-space",
                    native_workspace_id="native-space",
                    details_json={},
                    created_by="issuer|alice",
                )
            )
            for identifier, kind, parent in (
                ("local-source", "source", "folder"),
                ("local-asset", "document", "local-source"),
            ):
                session.add(
                    CatalogEntry(
                        id=identifier,
                        tenant_id="retained",
                        kind=kind,
                        name=identifier,
                        workspace_id="workspace",
                        project_id="project",
                        parent_id=parent,
                        created_by="issuer|alice",
                    )
                )
                await session.flush()
            session.add(
                DomainBinding(
                    id="local-binding",
                    tenant_id="retained",
                    catalog_id="local-asset",
                    workspace_id="workspace",
                    domain="canon",
                    entity_kind="document",
                    native_id="local-source",
                    native_workspace_id="native-space",
                    details_json={},
                    created_by="issuer|alice",
                )
            )
            for identifier, digest, filename in (
                ("native-source", "d" * 64, "Protected imported filename.txt"),
                ("local-source", "e" * 64, "Local filename.txt"),
            ):
                session.add(
                    SourceRow(
                        id=identifier,
                        tenant_id="retained",
                        workspace_id="native-space",
                        kind="text",
                        status="ingested",
                        filename=filename,
                        content_sha256=digest,
                        content_bytes=7,
                        metadata_json={},
                        n_chunks=1,
                    )
                )
        catalog = CatalogService(TenantRepository(), MembershipRepository(), CatalogRepository())
        records = SourceReadRepository()
        reader = SourceReader(
            SourceReadAuthority(records, SimpleNamespace(get=lambda: None), catalog),
            SourceReaderSelections(SourceReaderSelectionRepository(), catalog),
            records,
        )
        facade = KnowledgeFacade(
            catalog,
            DomainBindingRepository(),
            None,
            KnowledgeSettings(),
            source_reader=SimpleNamespace(get=lambda: reader),
        )
        if imported:
            with pytest.raises(SourceError):
                await facade.authorize_source_entries("issuer|alice", "retained", ("asset",))
        else:
            await facade.authorize_source_entries("issuer|alice", "retained", ("local-asset",))
        policies = LegacyOperationPolicies()
        LegacyReadAdmission(
            facade, registry, policies, SimpleNamespace(domains={"canon": {"registered": True}})
        )
        native = GetSourceHandler(SourceRepository(registry.get("canon").sessionmaker))
        projected = _projected(SourcesController, "canon.SourcesController", "/api/v1/canon/sources")
        controller = projected(None, SimpleNamespace(query=native.do_handle), None, None)
        hydrated = []

        async def endpoint(request):
            record = await controller.get_source(request, request.path_params["source_id"])
            hydrated.append(record.filename)
            return JSONResponse(record.model_dump(mode="json"))

        app = Starlette(routes=[Route("/api/v1/canon/sources/{source_id}", endpoint)])
        membership = LegacyMembershipFilter(catalog, policies)

        async def authenticated_member(request, call_next):
            request.state.security_context = SecurityContext(
                user_id="alice", attributes={"iss": "issuer", "sub": "alice"}
            )
            return await membership.do_filter(request, call_next)

        app.add_middleware(BaseHTTPMiddleware, dispatch=authenticated_member)

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get(
                "/api/v1/canon/sources/" + ("native-source" if imported else "local-source"),
                headers={
                    "X-Tenant-ID": "retained",
                    "X-Workspace-ID": "workspace",
                    "X-Correlation-ID": "legacy-proof",
                },
            )
        if imported:
            assert response.status_code in (403, 503), response.text
            assert hydrated == []
        else:
            assert response.status_code == 200, response.text
            assert response.json()["filename"] == "Local filename.txt"
            assert hydrated == ["Local filename.txt"]
    finally:
        await context.stop()
