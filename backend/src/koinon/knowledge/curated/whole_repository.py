# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Native serving-version projection queries through the context-owned datasource."""

from flycanon.core.services.query.rlm.knowledge_integrity import KNOWLEDGE_PART_CHARS, MAX_BODY_BYTES
from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeVersionMeta
from flycanon.models.entities.knowledge_item import KnowledgeItemRow
from flycanon.models.entities.knowledge_version import KnowledgeVersionRow
from pyfly.container import repository
from pyfly.data.relational.datasource_registry import DataSource, DataSourceRegistry
from pyfly.data.transaction import infrastructure_unit
from pyfly.kernel import ConflictException, ServiceUnavailableException
from sqlalchemy import Select, select, text

from koinon.knowledge.adapters import native_scope
from koinon.knowledge.capture_dtos import NativeDatabaseContext
from koinon.knowledge.curated.corpus_dtos import CuratedProjection
from koinon.knowledge.curated.corpus_mappers import part_record
from koinon.knowledge.curated.domain_entities import (
    CuratedCommitRow,
    CuratedEvidenceRow,
    CuratedHeadRow,
    CuratedVersionChunkRow,
)


def changed() -> ConflictException:
    return ConflictException(
        "The native published serving version changed", code="KNOWLEDGE_VERSION_CONFLICT"
    )


@repository(name="knowledge.curated.whole_parts")
class CuratedWholePartRepository:
    def __init__(self, datasources: DataSourceRegistry):
        self.datasources = datasources

    def _source(self) -> DataSource:
        try:
            return self.datasources.get("canon")
        except KeyError:
            raise ServiceUnavailableException(
                "Configure the native knowledge datasource", code="KNOWLEDGE_COMMIT_UNAVAILABLE"
            ) from None

    @staticmethod
    def _serving(meta: KnowledgeVersionMeta) -> Select[str]:
        version, item, head, evidence, commit = (
            KnowledgeVersionRow,
            KnowledgeItemRow,
            CuratedHeadRow,
            CuratedEvidenceRow,
            CuratedCommitRow,
        )
        return (
            select(version.id)
            .join(item, item.id == version.knowledge_item_id)
            .join(head, head.native_item_id == version.knowledge_item_id)
            .join(evidence, (evidence.native_version_id == version.id) & (evidence.ordinal == 1))
            .join(commit, commit.operation_id == evidence.operation_id)
            .where(
                version.id == meta.version_id,
                version.version == meta.version,
                version.knowledge_item_id == meta.native_item_id,
                version.status == "published",
                version.tenant_id == meta.tenant_id,
                version.workspace_id == meta.workspace_id,
                item.tenant_id == meta.tenant_id,
                item.workspace_id == meta.workspace_id,
                item.status != "retired",
                head.tenant_id == meta.tenant_id,
                head.workspace_id == meta.workspace_id,
                head.canonical_item_id == meta.item_id,
                head.canonical_workspace_id == meta.canonical_workspace_id,
                head.serving_version == meta.version,
                evidence.tenant_id == meta.tenant_id,
                evidence.workspace_id == meta.workspace_id,
                commit.tenant_id == meta.tenant_id,
                commit.workspace_id == meta.workspace_id,
                commit.canonical_item_id == meta.item_id,
                commit.operation_id == meta.operation_id,
                commit.subject == meta.author_subject,
                commit.receipt_json.is_not(None),
            )
        )

    async def assert_serving(self, meta: KnowledgeVersionMeta, *, subject: str) -> None:
        with native_scope("canon", meta.tenant_id, meta.workspace_id, subject):
            async with infrastructure_unit(self._source(), read_only=True) as session:
                if await session.scalar(self._serving(meta)) is None:
                    raise changed()

    async def read(self, meta: KnowledgeVersionMeta, *, subject: str) -> CuratedProjection:
        with native_scope("canon", meta.tenant_id, meta.workspace_id, subject):
            async with infrastructure_unit(self._source(), read_only=True) as session:
                if await session.scalar(self._serving(meta)) is None:
                    raise changed()
                chunk = CuratedVersionChunkRow
                rows = (
                    await session.execute(
                        select(chunk, KnowledgeVersionRow.knowledge_item_id)
                        .join(KnowledgeVersionRow, KnowledgeVersionRow.id == chunk.native_version_id)
                        .where(
                            chunk.tenant_id == meta.tenant_id,
                            chunk.workspace_id == meta.workspace_id,
                            chunk.native_version_id == meta.version_id,
                            KnowledgeVersionRow.tenant_id == meta.tenant_id,
                            KnowledgeVersionRow.workspace_id == meta.workspace_id,
                        )
                        .order_by(chunk.ordinal, chunk.id)
                        .limit(MAX_BODY_BYTES // KNOWLEDGE_PART_CHARS + 2)
                    )
                ).all()
                engine = session.get_bind().dialect.name
                identity = (
                    (
                        await session.execute(
                            text(
                                "SELECT current_database() AS database,current_catalog AS catalog,"
                                "current_schema() AS schema"
                            )
                        )
                    )
                    .mappings()
                    .one()
                    if engine == "postgresql"
                    else {}
                )
                context = NativeDatabaseContext(
                    engine, identity.get("database"), identity.get("catalog"), identity.get("schema")
                )
                return CuratedProjection(
                    tuple(part_record(row, native_item_id) for row, native_item_id in rows), context
                )
