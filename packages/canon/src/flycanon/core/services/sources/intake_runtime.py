# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Explicit managed dependencies for versioned source processing."""

from dataclasses import dataclass

from pyfly.agentic.content.binary import BinaryNormalizer
from pyfly.container import service
from pyfly.eda import EventPublisher

from flycanon.config import CanonSettings
from flycanon.core.services.audit import AuditService
from flycanon.core.services.embeddings import EmbeddingRegistry, EmbeddingService, EmbeddingSetService
from flycanon.core.services.ingestion import IngestionService
from flycanon.core.services.ingestion.loaders import LoaderRegistry
from flycanon.core.services.metadata import MetadataExtractor
from flycanon.core.services.pii import PiiPolicy, PiiScanner
from flycanon.core.services.retrieval import IndexService
from flycanon.core.services.sources.intake_policy import SourceIntakePolicy, build_intake_policy
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.models.repositories.chunk_repository import ChunkRepository
from flycanon.models.repositories.source_repository import SourceRepository


@service(name="canon.SourceIntakeComponents")
@dataclass(frozen=True)
class SourceIntakeComponents:
    binary_normalizer: BinaryNormalizer
    ingestion: IngestionService
    loaders: LoaderRegistry
    embeddings: EmbeddingService
    indexer: IndexService
    metadata_extractor: MetadataExtractor
    source_repository: SourceRepository
    chunk_repository: ChunkRepository
    audit: AuditService
    event_publisher: EventPublisher | None
    object_store: ObjectStore
    settings: CanonSettings
    policy: SourceIntakePolicy
    embedding_sets: EmbeddingSetService | None = None
    embedding_registry: EmbeddingRegistry | None = None

    @property
    def pii_policy(self) -> PiiPolicy:
        return self.policy.value

    @property
    def pii_scanner(self) -> PiiScanner | None:
        return self.policy.scanner


def build_intake_components(
    binary_normalizer: BinaryNormalizer,
    ingestion: IngestionService,
    loaders: LoaderRegistry,
    embeddings: EmbeddingService,
    indexer: IndexService,
    metadata_extractor: MetadataExtractor,
    source_repository: SourceRepository,
    chunk_repository: ChunkRepository,
    audit: AuditService,
    event_publisher: EventPublisher | None,
    object_store: ObjectStore,
    settings: CanonSettings,
    embedding_sets: EmbeddingSetService | None = None,
    embedding_registry: EmbeddingRegistry | None = None,
    intake_policy: SourceIntakePolicy | None = None,
) -> SourceIntakeComponents:
    return SourceIntakeComponents(
        policy=intake_policy or build_intake_policy(settings),
        binary_normalizer=binary_normalizer,
        ingestion=ingestion,
        loaders=loaders,
        embeddings=embeddings,
        indexer=indexer,
        metadata_extractor=metadata_extractor,
        source_repository=source_repository,
        chunk_repository=chunk_repository,
        audit=audit,
        event_publisher=event_publisher,
        object_store=object_store,
        settings=settings,
        embedding_sets=embedding_sets,
        embedding_registry=embedding_registry,
    )
