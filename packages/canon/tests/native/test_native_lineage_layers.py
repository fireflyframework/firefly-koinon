# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Layer boundaries preserve native transactions and immutable admission."""

import importlib
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pyfly.container import Container

from flycanon.core.services.sources.lineage.service import DocumentLineage
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.models.repositories.source_repository import SourceRepository


def layers():
    name = "flycanon.core.services.sources.lineage.ports"
    assert importlib.util.find_spec(name) is not None, "Lineage persistence needs an explicit typed port"
    return importlib.import_module(name)


async def test_managed_lineage_uses_the_injected_persistence_override():
    port = layers().LineagePersistence
    persistence = SimpleNamespace(require_schema=AsyncMock())
    sources, store = object(), object()
    container = Container()
    container.register_instance(SourceRepository, sources)
    container.register_instance(ObjectStore, store)
    container.register_instance(port, persistence)
    container.register(DocumentLineage)
    lineage = container.resolve(DocumentLineage)
    assert lineage.repository is persistence
    await lineage.require_schema()
    persistence.require_schema.assert_awaited_once()


async def test_pipeline_has_explicit_dependencies_without_reaching_into_intake():
    module = importlib.import_module("flycanon.core.services.sources.lineage.pipeline")
    lineage = SimpleNamespace(require_schema=AsyncMock(side_effect=RuntimeError("stop before work")))
    components = SimpleNamespace(settings=SimpleNamespace(store_originals=True, vector_store="pgvector"))
    pipeline = module.DocumentLineagePipeline(components=components, lineage=lineage)
    try:
        await pipeline.run(
            request=object(),
            content=b"raw",
            tenant_id="t",
            workspace_id="w",
            actor="actor",
            filename="one.txt",
            content_type="text/plain",
            logical_key="doc",
            operation_id="upload",
        )
    except RuntimeError as error:
        assert str(error) == "stop before work"
    else:
        raise AssertionError("The explicit lineage boundary must be used before transformation")
    lineage.require_schema.assert_awaited_once()


async def test_managed_intake_graph_shares_explicit_components_and_lineage():
    from pyfly.agentic.content.binary import BinaryNormalizer
    from pyfly.eda import EventPublisher

    from flycanon.config import CanonSettings
    from flycanon.core.services.audit import AuditService
    from flycanon.core.services.embeddings import EmbeddingService
    from flycanon.core.services.ingestion import IngestionService
    from flycanon.core.services.ingestion.loaders import LoaderRegistry
    from flycanon.core.services.metadata import MetadataExtractor
    from flycanon.core.services.retrieval import IndexService
    from flycanon.core.services.sources.intake_policy import SourceIntakePolicy, build_intake_policy
    from flycanon.core.services.sources.intake_runtime import SourceIntakeComponents
    from flycanon.core.services.sources.intake_service import IntakeService
    from flycanon.core.services.sources.lineage.pipeline import DocumentLineagePipeline
    from flycanon.models.repositories.chunk_repository import ChunkRepository

    container = Container()
    settings = CanonSettings(pii_policy="disabled")
    values = {
        CanonSettings: settings,
        SourceIntakePolicy: build_intake_policy(settings),
        BinaryNormalizer: object(),
        IngestionService: object(),
        LoaderRegistry: object(),
        EmbeddingService: object(),
        IndexService: object(),
        MetadataExtractor: object(),
        SourceRepository: object(),
        ChunkRepository: object(),
        AuditService: object(),
        EventPublisher: object(),
        ObjectStore: object(),
        DocumentLineage: object(),
    }
    for kind, value in values.items():
        container.register_instance(kind, value)
    for kind in (SourceIntakeComponents, DocumentLineagePipeline, IntakeService):
        container.register(kind)
    intake = container.resolve(IntakeService)
    pipeline = container.resolve(DocumentLineagePipeline)
    assert intake._lineage_pipeline is pipeline
    assert pipeline.components is container.resolve(SourceIntakeComponents)
    assert pipeline.lineage is values[DocumentLineage]
    assert pipeline.components.policy is values[SourceIntakePolicy]
    assert pipeline.components.pii_scanner is intake._pii_scanner
    assert pipeline.components.binary_normalizer is intake._binary_normalizer is values[BinaryNormalizer]
    assert pipeline.components.event_publisher is intake._publisher is values[EventPublisher]


async def test_admission_requires_new_transaction_survives_outer_rollback(tmp_path):
    import pytest
    from pyfly.core import Config
    from pyfly.data.relational.datasource_registry import DataSourceRegistry
    from pyfly.data.transaction import TransactionTemplate
    from sqlalchemy import text

    from flycanon.core.services.sources.lineage.dtos import DocumentScope
    from flycanon.core.services.storage.local_fs import LocalFsObjectStore
    from flycanon.models.entities import Base
    from flycanon.models.entities.source_lineage import metadata
    from flycanon.models.repositories.lineage.repository import NativeLineageRepository

    registry = DataSourceRegistry(
        Config(
            {
                "pyfly": {
                    "data": {
                        "relational": {
                            "url": f"sqlite+aiosqlite:///{tmp_path / 'native-lineage.db'}",
                        }
                    }
                }
            }
        )
    )
    source = registry.primary
    async with source.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(metadata.create_all)
        await connection.execute(text("DROP INDEX uq_canon_sources_tenant_workspace_content_sha256"))
    sources = SourceRepository(source.sessionmaker, engine=source.engine)
    lineage = DocumentLineage(
        sources, LocalFsObjectStore(str(tmp_path / "bytes")), NativeLineageRepository(sources)
    )
    scope = DocumentScope("tenant", "workspace", "owner")
    try:
        with pytest.raises(RuntimeError, match="outer failed"):
            async with TransactionTemplate(source, read_only=True).transaction():
                admission = await lineage.admit(
                    scope,
                    logical_key="document",
                    operation_id="upload",
                    content=b"raw",
                    filename="one.txt",
                    media_type="text/plain",
                )
                raise RuntimeError("outer failed")
        assert (await lineage.history(scope, admission.source_id)).total == 1
        assert (
            await lineage.original(scope, admission.source_id, admission.version_id, max_bytes=3)
        ).content == b"raw"
    finally:
        await registry.close()
