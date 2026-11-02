# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Owned PostgreSQL locks and native document lineage decide recovery, not missing IDs."""

import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pyfly.data.relational.datasource_registry import DataSourceRegistry
from pyfly.kernel import ConflictException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from test_bulk_native import bulk as bulk
from test_bulk_pinned_postgres import bulk_url as bulk_url
from test_bulk_pinned_postgres import load
from test_bulk_processing_recovery import failed_before_native

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.bulk.dtos import BulkRecoveryAction
from koinon.knowledge.bulk.native import NativeBulkIntake
from koinon.knowledge.bulk.queue import BulkQueue
from koinon.knowledge.bulk.repositories import BulkRepository
from koinon.knowledge.entities import DomainBinding
from koinon.knowledge.repositories import DomainBindingRepository
from koinon.knowledge.service import KnowledgeFacade, KnowledgeSettings

pytestmark = pytest.mark.integration


async def native_reader(bulk, bulk_url):
    from pathlib import Path

    from flycanon.core.services.sources.lineage.service import DocumentLineage
    from flycanon.data import TenantGucCustomizer
    from flycanon.models.entities.source import SourceRow
    from flycanon.models.repositories.source_repository import SourceRepository

    role = "bulk_recovery_reader_" + uuid4().hex[:12]
    root = Path(__file__).resolve().parents[4]
    engine = create_engine(make_url(bulk_url).set(drivername="postgresql+psycopg"))
    try:
        with engine.begin() as connection:
            SourceRow.__table__.create(connection)
            with Operations.context(MigrationContext.configure(connection)):
                for filename in (
                    "20261027_1600_0020_source_lineage.py",
                    "20261031_1800_0021_pinned_originals.py",
                ):
                    migration = load(
                        root / "packages/canon/migrations/koinon_versions" / filename, "recovery_lineage"
                    )
                    migration.upgrade()
            connection.execute(text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
            connection.execute(text(f'GRANT USAGE ON SCHEMA public TO "{role}"'))
            connection.execute(
                text(
                    "GRANT SELECT ON canon_source_versions,canon_source_artifacts,"
                    f'canon_source_extractions TO "{role}"'
                )
            )
    finally:
        engine.dispose()
    registry = bulk.context.get_bean(DataSourceRegistry)
    datasource = registry.register("canon_recovery", bulk_url)

    class ReaderRole:
        async def after_begin(self, connection, datasource):
            await connection.execute(text(f'SET LOCAL ROLE "{role}"'))

    registry.add_customizer(TenantGucCustomizer(datasource.name), datasource=datasource.name)
    registry.add_customizer(ReaderRole(), datasource=datasource.name)
    source_repository = SourceRepository(datasource.sessionmaker, engine=datasource.engine)
    lineage = DocumentLineage(source_repository, None)
    workspace = bulk.target["workspace_id"]
    with native_scope("canon", "north", workspace, "issuer|editor"):
        async with source_repository.session() as session:
            observed = (
                await session.execute(
                    text(
                        "SELECT current_user,current_setting('app.tenant_id'),"
                        "current_setting('app.workspace_id')"
                    )
                )
            ).one()
            assert tuple(observed) == (role, "north", workspace)
    bindings = bulk.context.get_bean(DomainBindingRepository)
    await bindings.save(
        DomainBinding(
            id=str(uuid4()),
            tenant_id="north",
            catalog_id=workspace,
            workspace_id=workspace,
            domain="canon",
            entity_kind="workspace",
            native_id=workspace,
            native_workspace_id=workspace,
            created_by="issuer|editor",
        )
    )
    records = bulk.context.get_bean(BulkRepository)
    records.workspace_matches = BulkRepository.workspace_matches.__get__(records, type(records))
    facade = KnowledgeFacade(
        bulk.catalog, bindings, SimpleNamespace(_resolve=lambda kind: lineage), KnowledgeSettings()
    )
    port = bulk.context.get_bean(NativeBulkIntake)
    port.facades = SimpleNamespace(get=lambda: facade)
    bulk.service.intakes = SimpleNamespace(get=lambda: port)
    return port


def sqlstate(error):
    visited = set()
    while error is not None and id(error) not in visited:
        visited.add(id(error))
        state = getattr(error, "sqlstate", None) or getattr(error, "pgcode", None)
        if state:
            return state
        error = getattr(error, "orig", None) or error.__cause__ or error.__context__
    return None


async def test_real_native_absence_and_concurrent_recovery_fence_the_late_old_generation(bulk, bulk_url):
    batch_id, item_id, old, _ = await failed_before_native(bulk)
    port = await native_reader(bulk, bulk_url)
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    assert descriptor.native_state == "absent" and descriptor.operation == "retry_processing"
    body = BulkRecoveryAction(expected_revision=descriptor.batch_revision, operation="retry_processing")
    inspected, release = asyncio.Event(), asyncio.Event()
    original = port.inspect

    async def held(lease):
        observation = await original(lease)
        inspected.set()
        await release.wait()
        return observation

    port.inspect = held
    first = asyncio.create_task(
        bulk.service.recover_processing("issuer|editor", "north", batch_id, item_id, body, "recover")
    )
    await asyncio.wait_for(inspected.wait(), 5)
    second = asyncio.create_task(
        bulk.service.recover_processing("issuer|editor", "north", batch_id, item_id, body, "recover")
    )
    effects = []

    async def late_old_generation():
        await bulk.context.get_bean(BulkQueue).check(old)
        effects.append("native-model-entry")

    old_task = asyncio.create_task(late_old_generation())
    await asyncio.sleep(0)
    assert not second.done()
    release.set()
    results = await asyncio.gather(first, second, old_task, return_exceptions=True)
    assert not isinstance(results[0], BaseException)
    assert not isinstance(results[1], BaseException) or sqlstate(results[1]) == "40001"
    assert isinstance(results[2], ConflictException) and results[2].code == "BULK_LEASE_LOST"
    assert effects == []
    replay = await bulk.service.recover_processing(
        "issuer|editor", "north", batch_id, item_id, body, "recover"
    )
    assert replay.status == "queued"
    new = await bulk.context.get_bean(BulkQueue).claim("new-worker")
    assert new.job_id == old.job_id and new.attempt == 2 and new.recovery_operation == "retry_processing"
    await bulk.context.get_bean(BulkQueue).check(new)


async def test_real_native_admission_is_not_absence_and_cannot_be_retried(bulk, bulk_url):
    batch_id, item_id, lease, _ = await failed_before_native(bulk)
    await native_reader(bulk, bulk_url)
    engine = create_engine(make_url(bulk_url).set(drivername="postgresql+psycopg"))
    try:
        with engine.begin() as connection:
            source, artifact, version = str(uuid4()), str(uuid4()), str(uuid4())
            values = dict(
                tenant="north",
                workspace=bulk.target["workspace_id"],
                source=source,
                artifact=artifact,
                version=version,
                digest=lease.sha256,
                logical=lease.source_id,
                operation="upload:" + lease.source_id,
            )
            connection.execute(
                text("""INSERT INTO canon_source_artifacts
                (id,tenant_id,workspace_id,source_id,role,sha256,bytes,object_key)
                VALUES(:artifact,:tenant,:workspace,:source,'original',:digest,8,'owned/original')"""),
                values,
            )
            connection.execute(
                text("""INSERT INTO canon_source_versions
                (id,tenant_id,workspace_id,source_id,artifact_id,logical_key,operation_id)
                VALUES(:version,:tenant,:workspace,:source,:artifact,:logical,:operation)"""),
                values,
            )
    finally:
        engine.dispose()
    descriptor = await bulk.service.processing_recovery("issuer|editor", "north", batch_id, item_id)
    assert descriptor.native_state == "admitted" and descriptor.operation is None
    with pytest.raises(ConflictException) as failure:
        await bulk.service.recover_processing(
            "issuer|editor",
            "north",
            batch_id,
            item_id,
            BulkRecoveryAction(expected_revision=descriptor.batch_revision, operation="retry_processing"),
            "recover",
        )
    assert failure.value.code == "BULK_NATIVE_OUTCOME_UNRESOLVED"
    assert await bulk.context.get_bean(BulkQueue).claim("new-worker") is None
