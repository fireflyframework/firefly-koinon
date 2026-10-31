# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Collision-safe corpus routing keeps document and knowledge identities distinct."""

from typing import TYPE_CHECKING

from flycanon.core.services.sources.lineage.dtos import DocumentCitationRef
from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeCitationRef, KnowledgeVersionMeta
from flycanon.interfaces.dtos.rlm_corpus import SourceMeta
from flycanon.interfaces.knowledge_corpus import RlmCorpus

if TYPE_CHECKING:
    from flycanon.core.services.query.rlm.knowledge_corpus import KnowledgeDocStore


class CombinedCorpus:
    def __init__(self, documents: RlmCorpus, knowledge: "KnowledgeDocStore"):
        self.documents, self.knowledge = documents, knowledge
        self._document_keys = tuple(documents.keys())
        self.accessed: list[str] = []

    def keys(self) -> list[str]:
        return ["document:" + key for key in self._document_keys] + self.knowledge.keys()

    def __iter__(self):
        return iter(self.keys())

    def __len__(self) -> int:
        return len(self._document_keys) + len(self.knowledge)

    def _route(self, key: str):
        self.knowledge.check_access()
        if key.startswith("document:") and key.removeprefix("document:") in self._document_keys:
            return self.documents, key.removeprefix("document:")
        if key in self.knowledge:
            return self.knowledge, key
        raise KeyError(key)

    def __contains__(self, key: object) -> bool:
        self.knowledge.check_access()
        return isinstance(key, str) and (
            key in ["document:" + value for value in self._document_keys] or key in self.knowledge
        )

    def resolve(self, key: str) -> SourceMeta | KnowledgeVersionMeta | None:
        if key not in self:
            return None
        corpus, following = self._route(key)
        return corpus.resolve(following)

    def _record(self, key: str) -> None:
        if key not in self.accessed:
            self.accessed.append(key)

    def __getitem__(self, key: str) -> str:
        corpus, following = self._route(key)
        result = corpus[following]
        self._record(key)
        return result

    def pages(self, key: str) -> list[str]:
        corpus, following = self._route(key)
        result = corpus.pages(following)
        self._record(key)
        return result

    def npages(self, key: str) -> int:
        corpus, following = self._route(key)
        return corpus.npages(following)

    def _execution_read(self, key: str, *, as_pages: bool) -> str | list[str]:
        corpus, following = self._route(key)
        result = corpus._execution_read(following, as_pages=as_pages)
        self._record(key)
        return result

    def citation_ref(
        self, key: str, page_index: int, quote: str
    ) -> DocumentCitationRef | KnowledgeCitationRef | None:
        corpus, following = self._route(key)
        return corpus.citation_ref(following, page_index, quote)
