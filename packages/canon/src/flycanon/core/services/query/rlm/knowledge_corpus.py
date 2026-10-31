# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Request-owned complete approved versions exposed only to the leased native RLM worker."""

from asyncio import get_running_loop, run_coroutine_threadsafe
from types import MappingProxyType
from typing import TYPE_CHECKING

from pyfly.kernel import ServiceUnavailableException

from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.combined_corpus import CombinedCorpus as CombinedCorpus
from flycanon.core.services.query.rlm.knowledge_integrity import KNOWLEDGE_PART_CHARS, verify_view
from flycanon.core.services.retrieval import curated_corpus
from flycanon.interfaces.dtos.knowledge_corpus import (
    KnowledgeCitationRef,
    KnowledgeVersionMeta,
    WholeKnowledgeRead,
)
from flycanon.interfaces.dtos.rlm_corpus import Filters
from flycanon.interfaces.knowledge_corpus import CuratedRlmReader

if TYPE_CHECKING:
    from flycanon.core.services.retrieval.curated_corpus import CorpusLease


def unavailable() -> ServiceUnavailableException:
    return ServiceUnavailableException(
        "The exact approved corpus scope is unavailable", code="KNOWLEDGE_CORPUS_SCOPE_EXPIRED"
    )


class KnowledgeDocStore:
    def __init__(
        self, metas: tuple[KnowledgeVersionMeta, ...], reader: CuratedRlmReader, lease: "CorpusLease"
    ):
        self._metas = MappingProxyType(
            {f"knowledge:{meta.item_id}@{meta.version_id}": meta for meta in metas}
        )
        if len(self._metas) != len(metas) or len(metas) > 128:
            raise unavailable()
        self._reader, self._lease = reader, lease
        self._views: dict[str, WholeKnowledgeRead] = {}
        self.accessed: list[str] = []

    def _scope(self):
        scope = provenance.current()
        if (
            scope is None
            or curated_corpus.current_lease() is not self._lease
            or not self._lease.active
            or not scope.active
            or scope.task is not self._lease.task
            or scope.task.done()
            or scope.task.cancelling()
            or (scope.tenant_id, scope.workspace_id, scope.actor)
            != (self._lease.tenant_id, self._lease.workspace_id, self._lease.actor)
        ):
            raise unavailable()
        return scope

    def check_access(self) -> None:
        scope = self._scope()
        try:
            owner_loop = get_running_loop() is scope.loop
        except RuntimeError:
            owner_loop = False
        if owner_loop:
            if not scope.authorized:
                raise unavailable()
        else:
            provenance.authority(scope)
            self._scope()

    def keys(self) -> list[str]:
        self.check_access()
        return list(self._metas)

    def __iter__(self):
        return iter(self.keys())

    def __len__(self) -> int:
        self.check_access()
        return len(self._metas)

    def __contains__(self, key: object) -> bool:
        self.check_access()
        return isinstance(key, str) and key in self._metas

    def resolve(self, key: str) -> KnowledgeVersionMeta | None:
        self.check_access()
        return self._metas.get(key)

    def npages(self, key: str) -> int:
        self.check_access()
        return (self._metas[key].body_chars + KNOWLEDGE_PART_CHARS - 1) // KNOWLEDGE_PART_CHARS

    def _load(self, key: str) -> WholeKnowledgeRead:
        scope = self._scope()
        try:
            owner_loop = get_running_loop() is scope.loop
        except RuntimeError:
            owner_loop = False
        if owner_loop:
            raise ServiceUnavailableException(
                "Read approved bodies in the leased RLM worker", code="KNOWLEDGE_RLM_WORKER_REQUIRED"
            )
        with scope.lock:
            self.check_access()
            meta = self._metas[key]
            value = self._views.get(key)
            if value is None:
                future = run_coroutine_threadsafe(self._reader.read(meta), scope.loop)
                try:
                    value = future.result(timeout=30)
                    self._scope()
                except BaseException:
                    future.cancel()
                    raise
            verify_view(value)
            if value.meta != meta:
                raise unavailable()
            hook = getattr(scope.observer, "knowledge_view_parts", None)
            if not callable(hook):
                raise unavailable()
            hook(meta, value, scope)
            self._scope()
            self._views[key] = value
            return value

    def _record(self, key: str) -> None:
        if key not in self.accessed:
            self.accessed.append(key)

    def __getitem__(self, key: str) -> str:
        value = self._load(key)
        self._record(key)
        return value.text

    def pages(self, key: str) -> list[str]:
        value = self._load(key)
        self._record(key)
        return [part.text for part in value.parts]

    def _execution_read(self, key: str, *, as_pages: bool) -> str | list[str]:
        value = self._load(key)
        provenance.knowledge_execution_read(value.meta, value)
        self._scope()
        self._record(key)
        return [part.text for part in value.parts] if as_pages else value.text

    def citation_ref(self, key: str, page_index: int, quote: str) -> KnowledgeCitationRef | None:
        self.check_access()
        value = self._views.get(key)
        if value is None or type(page_index) is not int or not 0 <= page_index < len(value.parts):
            return None
        verify_view(value)
        part = value.parts[page_index]
        if not isinstance(quote, str) or not quote or quote not in part.text:
            return None
        return KnowledgeCitationRef(value.meta, part.part_id, part.sha256)


def matches(meta: KnowledgeVersionMeta, filters: Filters) -> bool:
    return (
        (not filters.knowledge_item_ids or meta.native_item_id in filters.knowledge_item_ids)
        and (not filters.domains or meta.domain in filters.domains)
        and (not filters.tags or bool(set(filters.tags) & set(meta.tags)))
        and (not filters.statuses or "published" in filters.statuses)
        and not filters.jurisdictions
    )


async def build_knowledge_store(
    *, tenant_id: str, workspace_id: str, filters: Filters | None = None
) -> KnowledgeDocStore | None:
    lease = curated_corpus.rlm_lease(tenant_id=tenant_id, workspace_id=workspace_id)
    if lease is None or lease.rlm is None:
        return None
    scope = provenance.current()
    if scope is None:
        raise unavailable()
    metas = await lease.rlm.pin()
    await provenance.authorize()
    if any(
        type(meta) is not KnowledgeVersionMeta
        or (meta.tenant_id, meta.workspace_id) != (tenant_id, workspace_id)
        for meta in metas
    ):
        raise unavailable()
    store = KnowledgeDocStore(
        tuple(meta for meta in metas if matches(meta, filters or Filters())), lease.rlm, lease
    )
    store.check_access()
    return store
