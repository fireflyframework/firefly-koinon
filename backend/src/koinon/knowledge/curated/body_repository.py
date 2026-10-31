# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Lexical native projection queries, separate from admission and body mapping."""

from collections.abc import Mapping

from flycanon.core.services.retrieval.retrieval_service import Hit
from pyfly.container import repository
from sqlalchemy import func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from koinon.knowledge.curated.corpus_dtos import ServingVersion
from koinon.knowledge.curated.corpus_mappers import lexical_hit
from koinon.knowledge.curated.domain_entities import (
    CuratedCommitRow,
    CuratedEvidenceRow,
    CuratedHeadRow,
    CuratedVersionChunkRow,
)
from koinon.knowledge.curated.dtos import KnowledgeVersionView


@repository(name="knowledge.curated.body_projection")
class CuratedBodyProjectionRepository:
    async def ranked(
        self,
        session: AsyncSession,
        tenant_id: str,
        workspace_id: str,
        selected: Mapping[str, tuple[ServingVersion, KnowledgeVersionView]],
        query: str,
        limit: int,
    ) -> list[Hit]:
        from flycanon.models.entities.knowledge_item import KnowledgeItemRow
        from flycanon.models.entities.knowledge_version import KnowledgeVersionRow

        chunk, version, head, evidence, commit = (
            CuratedVersionChunkRow,
            KnowledgeVersionRow,
            CuratedHeadRow,
            CuratedEvidenceRow,
            CuratedCommitRow,
        )
        statement = (
            select(chunk, version)
            .join(version, version.id == chunk.native_version_id)
            .join(
                head,
                (head.native_item_id == version.knowledge_item_id)
                & (head.serving_version == version.version),
            )
            .join(KnowledgeItemRow, KnowledgeItemRow.id == head.native_item_id)
            .join(evidence, (evidence.native_version_id == version.id) & (evidence.ordinal == 1))
            .join(commit, commit.operation_id == evidence.operation_id)
            .where(
                chunk.tenant_id == tenant_id,
                chunk.workspace_id == workspace_id,
                version.tenant_id == tenant_id,
                version.workspace_id == workspace_id,
                head.tenant_id == tenant_id,
                head.workspace_id == workspace_id,
                evidence.tenant_id == tenant_id,
                evidence.workspace_id == workspace_id,
                commit.tenant_id == tenant_id,
                commit.workspace_id == workspace_id,
                KnowledgeItemRow.tenant_id == tenant_id,
                KnowledgeItemRow.workspace_id == workspace_id,
                KnowledgeItemRow.status != "retired",
                version.status == "published",
                commit.receipt_json.is_not(None),
                chunk.native_version_id.in_(tuple(selected)),
            )
        )
        if session.get_bind().dialect.name == "postgresql":
            vector = literal_column("canon_knowledge_version_chunks.tsv")
            parsed = func.plainto_tsquery("simple", query)
            statement = statement.where(vector.op("@@")(parsed)).order_by(
                func.ts_rank_cd(vector, parsed).desc(), chunk.id
            )
        else:
            statement = statement.where(
                func.lower(chunk.content).contains(query.lower(), autoescape=True)
            ).order_by(chunk.id)
        rows = (await session.execute(statement.limit(limit))).all()
        return [
            lexical_hit(part, native_version, *selected[part.native_version_id], ordinal)
            for ordinal, (part, native_version) in enumerate(rows, 1)
        ]
