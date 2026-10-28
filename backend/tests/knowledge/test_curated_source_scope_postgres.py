# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Opt-in actual PostgreSQL regression for destination/source transaction composition."""

import os
from hashlib import sha256
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pyfly.core import Config
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from sqlalchemy import insert, text

from koinon.evidence.dtos import SourceReference
from koinon.knowledge.adapters import NativeDomains, native_scope
from koinon.knowledge.document_part_receipts import verify_part_sources

pytestmark = pytest.mark.skipif(not os.getenv("KOINON_CURATED_SCOPE_POSTGRES_URL"), reason="owned PostgreSQL")


@pytest.fixture
async def pg_scope(tmp_path):
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.core.services.storage.object_store import ObjectStore
    from flycanon.data import TenantGucCustomizer
    from flycanon.models.entities.source_lineage import (
        source_artifacts,
        source_extractions,
        source_heads,
        source_parts,
        source_versions,
    )
    from flycanon.models.entities.workspace import Workspace
    from flycanon.models.repositories import SourceRepository
    from sqlalchemy.engine import make_url

    url = os.environ["KOINON_CURATED_SCOPE_POSTGRES_URL"]
    target = make_url(url)
    if not (
        target.host == "127.0.0.1"
        and target.port == 18783
        and (target.database or "").startswith("koinon_index_qualification_curated_")
    ):
        pytest.fail("Curated PostgreSQL fixtures require their dedicated owned database")
    registry = DataSourceRegistry.for_config(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": url,
                            "datasources": {"canon": {"url": url}},
                        }
                    }
                }
            }
        )
    )
    registry.add_customizer(TenantGucCustomizer("canon"), datasource="canon")
    datasource = registry.get("canon")
    store = LocalFsObjectStore(str(tmp_path))
    sources = SourceRepository(datasource.sessionmaker)

    class Domains(NativeDomains):
        def __init__(self):
            pass

        def _resolve(self, kind):
            return {SourceRepository: sources, ObjectStore: store}[kind]

    tenant, source_workspace, destination_workspace = (str(uuid4()) for _ in range(3))
    for workspace in (source_workspace, destination_workspace):
        with native_scope("canon", tenant, workspace, "qualification|owner"):
            async with infrastructure_unit(datasource) as session:
                session.add(Workspace(id=workspace, tenant_id=tenant, name="Owned qualification"))
    source, version, ingestion, extraction, section, part = (str(uuid4()) for _ in range(6))
    body = "The threshold is 47."
    digest = sha256(body.encode()).hexdigest()
    artifacts = {role: str(uuid4()) for role in ("raw", "normalized", "whole_document_view")}
    with native_scope("canon", tenant, source_workspace, "qualification|owner"):
        async with infrastructure_unit(datasource) as session:
            assert (
                await session.execute(
                    text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
                )
            ).one() == (False, False)
            scope = {"tenant_id": tenant, "workspace_id": source_workspace, "source_id": source}
            for role, identifier in artifacts.items():
                await store.put(identifier, body.encode())
                await session.execute(
                    insert(source_artifacts).values(
                        **scope,
                        id=identifier,
                        role=role,
                        sha256=digest,
                        bytes=len(body.encode()),
                        object_key=identifier,
                    )
                )
            await session.execute(
                insert(source_versions).values(
                    **scope,
                    id=version,
                    artifact_id=artifacts["raw"],
                    logical_key=source,
                    operation_id=source,
                    actor="qualification|owner",
                )
            )
            for identifier, purpose, projection in (
                (ingestion, "ingestion", {}),
                (
                    extraction,
                    "whole_document_read",
                    {
                        "view_representation": "utf8_pages_joined_newline.v1",
                        "page_basis": "recorded_loader",
                        "input_extraction_id": ingestion,
                        "output_artifact_id": artifacts["whole_document_view"],
                        "section_ids_by_page": [[section]],
                        "source_section_digests": {section: digest},
                    },
                ),
            ):
                await session.execute(
                    insert(source_extractions).values(
                        **scope,
                        id=identifier,
                        version_id=version,
                        purpose=purpose,
                        normalized_artifact_id=artifacts["normalized"],
                        implementation={},
                        coverage="file_section",
                        projection=projection,
                    )
                )
            for identifier, ext, role, kind in (
                (section, ingestion, "normalized", "section"),
                (part, extraction, "whole_document_view", "page"),
            ):
                await session.execute(
                    insert(source_parts).values(
                        **scope,
                        id=identifier,
                        extraction_id=ext,
                        artifact_id=artifacts[role],
                        kind=kind,
                        ordinal=0,
                        text=body,
                        sha256=digest,
                    )
                )
            await session.execute(
                insert(source_heads).values(
                    **scope, logical_key=source, version_id=version, extraction_id=ingestion
                )
            )
    reference = SourceReference(
        id=str(uuid4()),
        asset_id=str(uuid4()),
        kind="document",
        title="Owned source",
        source_version_id=version,
        extraction_id=extraction,
        source_part_id=part,
        source_part_sha256=digest,
        used_revision="source-part-sha256:" + digest,
        page_basis="recorded_loader",
        quote=body,
    )
    binding = SimpleNamespace(native_id=source, native_workspace_id=source_workspace)

    async def authorize(values=None):
        if values is not None:
            assert all(ref.asset_id == reference.asset_id and bound is binding for ref, bound in values)

    try:
        yield SimpleNamespace(
            registry=registry,
            datasource=datasource,
            domains=Domains(),
            tenant=tenant,
            workspace=destination_workspace,
            reference=reference,
            binding=binding,
            authorize=authorize,
        )
    finally:
        await registry.close()


async def test_exact_cross_workspace_parts_join_destination_without_losing_source_admission(pg_scope):
    fixture = pg_scope
    with native_scope("canon", fixture.tenant, fixture.workspace, "qualification|owner"):
        async with infrastructure_unit(fixture.datasource) as session:
            before = (
                await session.execute(
                    text("SELECT current_setting('app.tenant_id'), current_setting('app.workspace_id')")
                )
            ).one()
            result = await verify_part_sources(
                fixture.domains,
                "qualification|owner",
                fixture.tenant,
                [(fixture.reference, fixture.binding)],
                current=True,
                lock=True,
                authorize=fixture.authorize,
            )
            assert result[fixture.reference.id].availability == "available"
            assert (
                await session.execute(
                    text("SELECT current_setting('app.tenant_id'), current_setting('app.workspace_id')")
                )
            ).one() == before


async def test_scoped_source_restores_nested_error_cancel_and_rejects_foreign_tenant(pg_scope):
    import asyncio

    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.source_scope import document_source_scope

    fixture = pg_scope
    with native_scope("canon", fixture.tenant, fixture.workspace, "qualification|owner"):
        async with infrastructure_unit(fixture.datasource) as session:

            async def workspace():
                return await session.scalar(text("SELECT current_setting('app.workspace_id')"))

            assert await workspace() == fixture.workspace
            async with document_source_scope(
                fixture.tenant, fixture.binding.native_workspace_id, authorize=fixture.authorize
            ):
                assert await workspace() == fixture.binding.native_workspace_id
                async with document_source_scope(
                    fixture.tenant, "nested-workspace", authorize=fixture.authorize
                ):
                    assert await workspace() == "nested-workspace"
                assert await workspace() == fixture.binding.native_workspace_id
            assert await workspace() == fixture.workspace
            with pytest.raises(RuntimeError, match="controlled"):
                async with document_source_scope(
                    fixture.tenant, fixture.binding.native_workspace_id, authorize=fixture.authorize
                ):
                    raise RuntimeError("controlled")
            assert await workspace() == fixture.workspace
            with pytest.raises(asyncio.CancelledError):
                async with document_source_scope(
                    fixture.tenant, fixture.binding.native_workspace_id, authorize=fixture.authorize
                ):
                    asyncio.current_task().cancel()
                    await asyncio.sleep(0)
            assert await workspace() == fixture.workspace
            with pytest.raises(AccessDenied):
                async with document_source_scope("foreign-tenant", fixture.binding.native_workspace_id):
                    pytest.fail("Foreign tenant entered source scope")
            assert await workspace() == fixture.workspace


async def test_source_scope_serializes_other_session_users_and_defers_pending_destination_flush(pg_scope):
    import asyncio

    from koinon.knowledge.curated.domain_entities import CuratedCommitRow
    from koinon.knowledge.curated.source_scope import document_source_scope

    fixture = pg_scope
    with native_scope("canon", fixture.tenant, fixture.workspace, "qualification|owner"):
        async with infrastructure_unit(fixture.datasource) as session:
            row = CuratedCommitRow(
                operation_id=str(uuid4()),
                canonical_item_id=str(uuid4()),
                subject="qualification|owner",
                tenant_id=fixture.tenant,
                workspace_id=fixture.workspace,
                authorization_digest="a" * 64,
                originating_token_ids=[],
            )
            session.add(row)
            started = asyncio.Event()

            async def concurrent_destination():
                started.set()
                return await session.scalar(text("SELECT current_setting('app.workspace_id')"))

            async with document_source_scope(
                fixture.tenant, fixture.binding.native_workspace_id, authorize=fixture.authorize
            ):
                task = asyncio.create_task(concurrent_destination())
                await started.wait()
                assert not task.done()
                result = await verify_part_sources(
                    fixture.domains,
                    "qualification|owner",
                    fixture.tenant,
                    [(fixture.reference, fixture.binding)],
                    current=True,
                    lock=True,
                    authorize=fixture.authorize,
                )
                assert result[fixture.reference.id].availability == "available"
                assert row in session.new
            assert await task == fixture.workspace
            await session.flush()
            assert (
                await session.scalar(
                    text("SELECT workspace_id FROM canon_knowledge_commits WHERE operation_id=:id"),
                    {"id": row.operation_id},
                )
                == fixture.workspace
            )


async def test_exact_source_lock_survives_scope_restore_until_destination_commit(pg_scope):
    from pyfly.data.transaction import outside_transaction
    from sqlalchemy.exc import DBAPIError

    fixture = pg_scope

    async def competing_update(expect_block):
        with (
            outside_transaction(),
            native_scope("canon", fixture.tenant, fixture.binding.native_workspace_id, "qualification|owner"),
        ):
            try:
                async with infrastructure_unit(fixture.datasource) as session:
                    await session.execute(text("SET LOCAL lock_timeout='150ms'"))
                    await session.execute(
                        text("UPDATE canon_source_heads SET logical_key=logical_key WHERE source_id=:source"),
                        {"source": fixture.binding.native_id},
                    )
            except DBAPIError as error:
                assert expect_block and error.orig.sqlstate == "55P03"
                return
            assert not expect_block

    with native_scope("canon", fixture.tenant, fixture.workspace, "qualification|owner"):
        async with infrastructure_unit(fixture.datasource) as session:
            await verify_part_sources(
                fixture.domains,
                "qualification|owner",
                fixture.tenant,
                [(fixture.reference, fixture.binding)],
                current=True,
                lock=True,
                authorize=fixture.authorize,
            )
            assert (
                await session.scalar(text("SELECT current_setting('app.workspace_id')")) == fixture.workspace
            )
            await competing_update(True)
        await competing_update(False)


async def test_database_error_in_source_scope_cannot_commit_pending_destination_write(pg_scope):
    from sqlalchemy import func, select
    from sqlalchemy.exc import DBAPIError

    from koinon.knowledge.curated.domain_entities import CuratedCommitRow
    from koinon.knowledge.curated.source_scope import document_source_scope

    fixture = pg_scope
    operation = str(uuid4())
    with native_scope("canon", fixture.tenant, fixture.workspace, "qualification|owner"):
        with pytest.raises(DBAPIError):
            async with infrastructure_unit(fixture.datasource) as session:
                session.add(
                    CuratedCommitRow(
                        operation_id=operation,
                        canonical_item_id=str(uuid4()),
                        subject="qualification|owner",
                        tenant_id=fixture.tenant,
                        workspace_id=fixture.workspace,
                        authorization_digest="b" * 64,
                        originating_token_ids=[],
                    )
                )
                async with document_source_scope(
                    fixture.tenant, fixture.binding.native_workspace_id, authorize=fixture.authorize
                ):
                    await session.execute(text("SELECT 1/0"))
        async with infrastructure_unit(fixture.datasource, read_only=True) as session:
            assert (
                await session.scalar(text("SELECT current_setting('app.workspace_id')")) == fixture.workspace
            )
            assert (
                await session.scalar(
                    select(func.count())
                    .select_from(CuratedCommitRow)
                    .where(CuratedCommitRow.operation_id == operation)
                )
                == 0
            )


async def test_source_scope_without_explicit_authority_cannot_rebind_same_tenant_workspace(pg_scope):
    from koinon.catalog.errors import AccessDenied
    from koinon.knowledge.curated.source_scope import document_source_scope

    fixture = pg_scope
    with native_scope("canon", fixture.tenant, fixture.workspace, "qualification|owner"):
        async with infrastructure_unit(fixture.datasource) as session:

            async def denied():
                raise AccessDenied("Controlled source authority denial")

            for authorize in (None, denied):
                with pytest.raises(AccessDenied):
                    async with document_source_scope(
                        fixture.tenant, fixture.binding.native_workspace_id, authorize=authorize
                    ):
                        pytest.fail("Unadmitted cross-workspace helper rebind")
                assert (
                    await session.scalar(text("SELECT current_setting('app.workspace_id')"))
                    == fixture.workspace
                )


async def test_postgres_destination_rls_denies_unscoped_source_read_and_foreign_workspace_insert(pg_scope):
    from sqlalchemy.exc import DBAPIError

    fixture = pg_scope
    with native_scope("canon", fixture.tenant, fixture.workspace, "qualification|owner"):
        async with infrastructure_unit(fixture.datasource) as session:
            assert (
                await session.scalar(
                    text("SELECT count(*) FROM canon_source_versions WHERE id=:id"),
                    {"id": fixture.reference.source_version_id},
                )
                == 0
            )
            with pytest.raises(DBAPIError) as failure:
                async with session.begin_nested():
                    await session.execute(
                        text(
                            "INSERT INTO canon_source_artifacts"
                            "(id,tenant_id,workspace_id,source_id,role,sha256,bytes,object_key) "
                            "VALUES(:id,:tenant,:workspace,:source,'raw',:sha,1,'qualification-denied')"
                        ),
                        {
                            "id": str(uuid4()),
                            "tenant": fixture.tenant,
                            "workspace": fixture.binding.native_workspace_id,
                            "source": fixture.binding.native_id,
                            "sha": "f" * 64,
                        },
                    )
            assert failure.value.orig.sqlstate == "42501"
            assert (
                await session.scalar(text("SELECT current_setting('app.workspace_id')")) == fixture.workspace
            )
