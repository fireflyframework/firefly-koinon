# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable operation binding over one managed reader; no model or publication service."""

from dataclasses import dataclass, field

from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeVersionMeta, WholeKnowledgeRead
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.curated.whole import CuratedWholeVersionReader


@dataclass(frozen=True, slots=True)
class BoundCuratedRlmReader:
    reader: CuratedWholeVersionReader = field(repr=False)
    subject: str
    tenant_id: str
    metas: tuple[KnowledgeVersionMeta, ...]

    async def pin(self) -> tuple[KnowledgeVersionMeta, ...]:
        await self.authorize()
        return self.metas

    async def authorize(self) -> None:
        await self.reader.authorize(self.subject, self.tenant_id, self.metas)

    async def read(self, meta: KnowledgeVersionMeta) -> WholeKnowledgeRead:
        if meta not in self.metas:
            raise ServiceUnavailableException(
                "The version is outside this admitted corpus", code="EVIDENCE_UNAVAILABLE"
            )
        return await self.reader.read(self.subject, self.tenant_id, meta)
