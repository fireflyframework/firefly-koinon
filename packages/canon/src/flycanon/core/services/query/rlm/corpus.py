# Copyright 2024-2026 Firefly Software Foundation
# Modifications Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""The corpus the RLM engine inspects as a variable.

RLM's premise is "context as an object in code": rather than pasting documents
into the prompt, the whole corpus is handed to the orchestrator as the variable
``docs``, which it inspects with Python. :class:`CanonDocStore` is that variable
-- a synchronous, in-memory dict-like over the in-scope workspace sources.
``docs.keys()`` lists readable document keys (derived from each source's
filename), ``docs[key]`` returns the full document text, ``docs.pages(key)``
returns its page list for precise citation, and every access is recorded so the
caller can map what the model touched back to source rows for citations.

The store is synchronous because the engine runs it in a leased worker.
Versioned product sources pin the immutable ledger and persist a regrouped
view of full ingestion sections before exposing content. Normalization and
PII are preserved; this is not a fresh raw-file extraction. Standalone legacy
sources retain their original-loader path. Metadata enumeration fetches no
document bytes and creates no content-extraction receipt.

``CanonDocStore`` structurally satisfies the ``DocCorpus`` protocol defined in
``session.py`` (it is not imported here -- the engine duck-types ``docs``).
"""

from __future__ import annotations

import hashlib
import inspect
import json
import logging
from asyncio import get_running_loop, run_coroutine_threadsafe
from collections.abc import Sequence
from dataclasses import dataclass, replace
from functools import lru_cache
from importlib.metadata import distributions
from types import MappingProxyType

from pyfly.kernel import ServiceUnavailableException

from flycanon.core.services.ingestion.loaders import LoaderRegistry, default_registry
from flycanon.core.services.query import provenance
from flycanon.core.services.query.rlm.page_cache import CorpusPageCache
from flycanon.core.services.sources.lineage.dtos import DocumentCitationRef, DocumentScope, WholeDocumentRead
from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader
from flycanon.core.services.storage.object_store import ObjectStore
from flycanon.interfaces.enums import SourceKind
from flycanon.models.entities.source import SourceRow
from flycanon.models.repositories.knowledge_repository import KnowledgeRepository
from flycanon.models.repositories.source_repository import SourceRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class SourceMeta:
    """The source pointer kept alongside each document for citations.

    Mirrors the citation-relevant fields the RAG ``Hit`` carries
    (``source_id`` / ``source_filename`` / ``source_title`` /
    ``source_kind``) so the answer service can hydrate citations the same
    way regardless of which retrieval engine produced them.
    """

    source_id: str
    filename: str | None
    title: str | None
    kind: str
    object_store_key: str
    # Compatibility pipeline-input hash; this is not the raw original identity.
    content_sha256: str
    tenant_id: str = ""
    workspace_id: str = ""
    raw_sha256: str | None = None
    raw_bytes: int | None = None
    source_version_id: str | None = None
    ingestion_extraction_id: str | None = None


class CanonDocStore:
    """Lazy, synchronous whole-document corpus for the RLM REPL.

    Holds a ``{readable_key: SourceMeta}`` map describing every in-scope
    filing -- listed cheaply by the builder, with no original fetched yet --
    plus the :class:`ObjectStore` and loader registry needed to materialise a
    filing on demand. Metadata methods perform no I/O. Content methods use
    the pinned immutable read wrapper for versioned sources, or the legacy
    original loader for standalone sources, then memoize pages per query.

    A shared :class:`CorpusPageCache` (optional) avoids repeated extraction
    after verifying original bytes and the scoped reader identity. The
    per-store ``_pages`` memo stays the innermost per-query layer.

    ``accessed`` records, in order, the keys the model touched via
    ``__getitem__`` / ``pages`` -- exactly like the experiment's ``DocStore`` --
    so the caller can credit the sources the model actually read.
    """

    def __init__(
        self,
        sources: dict[str, SourceMeta],
        *,
        object_store: ObjectStore,
        registry: LoaderRegistry,
        cache: CorpusPageCache | None = None,
        whole_reader: WholeDocumentReader | None = None,
    ) -> None:
        self._sources = MappingProxyType(dict(sources))
        self._object_store = object_store
        self._registry = registry
        self._cache = cache
        self._pages: dict[str, list[str]] = {}  # memoised per-key page lists
        self._whole_reader = whole_reader
        self._read_receipts: dict[str, WholeDocumentRead] = {}
        self.accessed: list[str] = []  # ordered, deduped: keys the model touched

    # -- dict-like surface the model uses from REPL code (metadata only, no I/O) --
    def keys(self):
        return list(self._sources.keys())

    def __iter__(self):
        return iter(self._sources)

    def __contains__(self, key: object) -> bool:
        return key in self._sources

    def __len__(self) -> int:
        return len(self._sources)

    # -- lazy page access: fetches + extracts on first touch, memoised --
    def __getitem__(self, key: str) -> str:
        """Full document text (pages joined). Fetches on first access; records it."""
        self._record(key)
        return "\n".join(self._load(key))

    def pages(self, key: str) -> list[str]:
        """Per-page text for ``key`` (for citing specific pages). Fetches on first access; records it."""
        self._record(key)
        return list(self._load(key))

    def npages(self, key: str) -> int:
        return len(self._load(key))

    # -- citation mapping --
    def resolve(self, key: str) -> SourceMeta | None:
        """Source pointer behind ``key`` (for citations), or ``None``."""
        return self._sources.get(key)

    def citation_ref(self, key: str, page_index: int, quote: str) -> DocumentCitationRef | None:
        """Resolve an already-read page; no lazy read or current-source substitution."""
        scope = provenance.current()
        meta, read = self._sources.get(key), self._read_receipts.get(key)
        if (
            scope is None
            or meta is None
            or (meta.tenant_id, meta.workspace_id) != (scope.tenant_id, scope.workspace_id)
        ):
            raise ServiceUnavailableException(
                "Current document citation scope is required", code="EVIDENCE_UNAVAILABLE"
            )
        if scope.allowed_sources is not None and meta.source_id not in scope.allowed_sources:
            raise ServiceUnavailableException("Document citation scope changed", code="EVIDENCE_UNAVAILABLE")
        if read is None or type(page_index) is not int or not 0 <= page_index < len(read.pages):
            return None
        if (
            read.source_version_id != meta.source_version_id
            or read.ingestion_extraction_id != meta.ingestion_extraction_id
        ):
            raise ServiceUnavailableException(
                "Document citation differs from its pinned view", code="EVIDENCE_UNAVAILABLE"
            )
        page = read.pages[page_index]
        if not isinstance(quote, str) or not quote or quote not in page.text:
            return None
        return DocumentCitationRef(
            meta.source_id,
            read.source_version_id,
            read.extraction_id,
            page.part_id,
            page.sha256,
            page.page,
            page.page_basis,
        )

    # -- internals --
    def _load(self, key: str) -> list[str]:
        scope = provenance.current()
        if scope is None:
            if self._sources[key].source_version_id is not None:
                raise ServiceUnavailableException(
                    "A current document provenance observer is required", code="EVIDENCE_UNAVAILABLE"
                )
            return self._load_pages(key)
        with scope.lock:
            provenance.authority(scope)
            meta = self._sources[key]
            if (meta.tenant_id, meta.workspace_id) != (scope.tenant_id, scope.workspace_id) or (
                scope.allowed_sources is not None and meta.source_id not in scope.allowed_sources
            ):
                raise ServiceUnavailableException("Native corpus scope mismatch", code="EVIDENCE_UNAVAILABLE")
            hook = getattr(scope.observer, "document_extraction", None)
            if meta.source_version_id is not None and not callable(hook):
                raise ServiceUnavailableException(
                    "The exact document extraction observer is required", code="EVIDENCE_UNAVAILABLE"
                )
            pages = self._load_pages(key)
            if meta.source_version_id is not None and callable(hook):
                receipt = self._read_receipts[key]
                hook(meta.source_id, receipt.source_version_id, receipt.extraction_id, scope)
            scope.source_ids.add(str(meta.source_id))
            scope.observer.document_sync("rlm.read", "\n".join(pages), (str(meta.source_id),), scope)
            return pages

    def _load_pages(self, key: str) -> list[str]:
        """Resolve the pinned recorded view, or the standalone original path.

        Original bytes are verified before a shared cache lookup. Unknown
        originals/readers bypass shared caching rather than borrowing pages.
        """
        cached = self._pages.get(key)
        if cached is not None:
            return cached
        meta = self._sources[key]  # KeyError for an unknown key, like a dict
        if meta.source_version_id is not None:
            return self._load_versioned(key, meta)
        data = self._object_store.get_sync(meta.object_store_key)
        cache_key = _cache_key(meta, data, self._registry)
        if self._cache is not None and cache_key is not None:
            shared = self._cache.get(cache_key)
            if shared is not None:
                self._pages[key] = shared
                return shared
        pages = _pages_for(meta, data, self._registry)
        if self._cache is not None and cache_key is not None:
            self._cache.set(cache_key, pages)
        self._pages[key] = pages
        return pages

    def _load_versioned(self, key: str, meta: SourceMeta) -> list[str]:
        scope = provenance.current()
        if (
            scope is None
            or self._whole_reader is None
            or meta.ingestion_extraction_id is None
            or meta.source_version_id is None
        ):
            raise ServiceUnavailableException(
                "The exact document version reader is required", code="DOCUMENT_EXTRACTION_UNAVAILABLE"
            )
        try:
            running_loop = get_running_loop()
        except RuntimeError:
            running_loop = None
        if running_loop is scope.loop:
            raise ServiceUnavailableException(
                "Whole-document views must be read in the leased RLM worker",
                code="DOCUMENT_EXTRACTION_WORKER_REQUIRED",
            )
        future = run_coroutine_threadsafe(
            self._whole_reader.read(
                DocumentScope(scope.tenant_id, scope.workspace_id, scope.actor),
                source_id=meta.source_id,
                source_version_id=meta.source_version_id,
                ingestion_extraction_id=meta.ingestion_extraction_id,
                authorize=scope.observer.authorize,
            ),
            scope.loop,
        )
        try:
            receipt = future.result(timeout=30)
            provenance.current()
        except BaseException:
            future.cancel()
            raise
        self._read_receipts[key] = receipt
        self._pages[key] = [page.text for page in receipt.pages]
        return self._pages[key]

    def _record(self, key: str) -> None:
        if key in self._sources and key not in self.accessed:
            self.accessed.append(key)


class CanonCorpusBuilder:
    """Builds a :class:`CanonDocStore` from the in-scope workspace sources.

    Lists the workspace's sources (applying the ``AnswerRequest`` filters with
    the same AND / no-op semantics as the RAG retrieval path) and collects only
    metadata and immutable version pins. No document bytes or content views
    are created here. Required product scopes refuse unknown legacy lineage;
    standalone sources without originals remain skipped as before.
    """

    def __init__(
        self,
        *,
        source_repository: SourceRepository,
        knowledge_repository: KnowledgeRepository,
        object_store: ObjectStore,
        registry: LoaderRegistry | None = None,
        cache: CorpusPageCache | None = None,
    ) -> None:
        self._sources = source_repository
        self._knowledge = knowledge_repository
        self._object_store = object_store
        self._registry = registry or default_registry()
        self._cache = cache  # shared page cache passed through to each store

    async def build(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        filters: Filters | None = None,
    ) -> CanonDocStore:
        from flycanon.core.agents.model_bindings import current_scope
        from flycanon.core.services.sources.lineage.service import DocumentLineage

        rows = await self._list_in_scope(tenant_id, workspace_id, filters)
        binding = current_scope()
        required = binding is not None and binding.required
        observation = provenance.current()
        whole_reader = None
        sources: dict[str, SourceMeta] = {}
        used_keys: set[str] = set()
        for row in rows:
            versioned = required or bool((row.metadata_json or {}).get("_source_lineage"))
            meta = _source_meta(row)
            if versioned:
                if row.status != "ingested":
                    continue
                if observation is None:
                    raise ServiceUnavailableException(
                        "A current document provenance observer is required", code="EVIDENCE_UNAVAILABLE"
                    )
                if (observation.tenant_id, observation.workspace_id) != (tenant_id, str(workspace_id)) or (
                    observation.allowed_sources is not None and str(row.id) not in observation.allowed_sources
                ):
                    raise ServiceUnavailableException(
                        "Native corpus scope mismatch", code="EVIDENCE_UNAVAILABLE"
                    )
                if whole_reader is None:
                    await observation.observer.authorize()
                    whole_reader = WholeDocumentReader(DocumentLineage(self._sources, self._object_store))
                pin = await whole_reader.pin(
                    DocumentScope(tenant_id, str(workspace_id), observation.actor), str(row.id)
                )
                meta = replace(
                    meta,
                    object_store_key="",
                    filename=pin.filename,
                    kind=pin.kind,
                    content_sha256=pin.normalized_sha256,
                    raw_sha256=pin.raw_sha256,
                    raw_bytes=pin.raw_bytes,
                    source_version_id=pin.source_version_id,
                    ingestion_extraction_id=pin.ingestion_extraction_id,
                )
            elif not row.object_store_key:
                logger.info(
                    "rlm corpus skipping source without stored original source_id=%s filename=%s",
                    row.id,
                    row.filename,
                )
                continue
            key = self._readable_key(row, used_keys)
            used_keys.add(key)
            sources[key] = meta
        return CanonDocStore(
            sources,
            object_store=self._object_store,
            registry=self._registry,
            cache=self._cache,
            whole_reader=whole_reader,
        )

    async def _list_in_scope(
        self,
        tenant_id: str,
        workspace_id: str,
        filters: Filters | None,
    ) -> list[SourceRow]:
        """Workspace sources after applying the filters (AND, empty = no-op).

        ``statuses`` is pushed into the repository query (it is a first-class
        ``SourceRow`` column); the remaining dimensions live on
        ``metadata_json`` (``domain`` / ``jurisdiction`` / ``tags``, mirroring
        the RAG hydration) or are the row id, so they are matched in-process.

        ``knowledge_item_ids`` is the one dimension that needs a repo
        round-trip: it is resolved to the set of ``source_id``\\ s that those
        items' **current-version** citations point at -- the whole-document,
        source-keyed analogue of the retrieval path's chunk-level
        ``knowledge_item_ids`` filter -- and AND-composed with the rest. An
        empty resolution (the items cite nothing) restricts the corpus to
        nothing, matching the RAG path where no hit would survive the filter.
        """
        f = filters or Filters()
        knowledge_source_ids = (
            await self._knowledge.resolve_source_ids_for_items(
                f.knowledge_item_ids,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
            )
            if f.knowledge_item_ids
            else None
        )
        rows: list[SourceRow] = []
        offset = 0
        page = 200
        while True:
            batch, total = await self._sources.list_sources(
                statuses=list(f.statuses) if f.statuses else None,
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                limit=page,
                offset=offset,
            )
            rows.extend(batch)
            offset += len(batch)
            if not batch or offset >= total:
                break
        return [row for row in rows if _matches(row, f, knowledge_source_ids)]

    def _readable_key(self, row: SourceRow, used: set[str]) -> str:
        """A routing-friendly key from the filename stem (fallbacks: title, id).

        De-duplicated across sources by suffixing ``#2``, ``#3`` ... so two
        files sharing a stem stay distinct keys.
        """
        base = _key_base(row)
        if base not in used:
            return base
        n = 2
        while f"{base}#{n}" in used:
            n += 1
        return f"{base}#{n}"


@dataclass(slots=True)
class Filters:
    """Corpus-scoping filters -- the ``AnswerRequest`` filter fields.

    Compose with AND; empty / ``None`` is a no-op, mirroring the RAG
    ``_Filters`` semantics. The values are plain strings (the caller passes
    enum ``.value``\\ s, as the RAG search service does).
    """

    source_ids: Sequence[str] | None = None
    knowledge_item_ids: Sequence[str] | None = None
    domains: Sequence[str] | None = None
    jurisdictions: Sequence[str] | None = None
    tags: Sequence[str] | None = None
    statuses: Sequence[str] | None = None


def _matches(row: SourceRow, f: Filters, knowledge_source_ids: set[str] | None) -> bool:
    """Whether a source row passes the in-process filter dimensions.

    ``source_ids`` matches the row id; ``domains`` / ``jurisdictions`` / ``tags``
    read the source's ``metadata_json`` hints (the same keys the RAG hydration
    falls back to when no knowledge linkage exists). ``knowledge_item_ids`` is
    pre-resolved by the caller to ``knowledge_source_ids`` -- the set of
    ``source_id``\\ s those items' current-version citations point at -- which
    the row id must be in (``None`` means the filter is absent / a no-op; an
    empty set means the items cite nothing, so nothing matches).
    """
    if f.source_ids and row.id not in set(f.source_ids):
        return False
    if knowledge_source_ids is not None and row.id not in knowledge_source_ids:
        return False
    meta = row.metadata_json or {}
    if f.domains and str(meta.get("domain")) not in set(f.domains):
        return False
    if f.jurisdictions and str(meta.get("jurisdiction")) not in set(f.jurisdictions):
        return False
    if f.tags:
        row_tags = {str(t) for t in (meta.get("tags") or [])}
        if not (set(f.tags) & row_tags):
            return False
    return True


@lru_cache(maxsize=1)
def _reader_dependencies() -> tuple[tuple[str, str], ...]:
    return tuple(sorted((dist.metadata.get("Name", ""), dist.version) for dist in distributions()))


def _cache_key(meta: SourceMeta, data: bytes, registry: LoaderRegistry) -> str | None:
    if not meta.raw_sha256 or meta.raw_bytes is None:
        return None
    if len(data) != meta.raw_bytes or hashlib.sha256(data).hexdigest() != meta.raw_sha256:
        raise ServiceUnavailableException(
            "Document original failed integrity verification", code="EVIDENCE_UNAVAILABLE"
        )
    if not all((meta.tenant_id, meta.workspace_id, meta.source_id)):
        return None
    loader = registry.get(_source_kind(meta.kind))
    # OCR also depends on external engines/models not described by Python metadata.
    if (
        loader is None
        or type(loader).__module__ != "flycanon.core.services.ingestion.loaders"
        or type(loader).__name__ in {"PdfLoader", "ImageLoader"}
    ):
        return None
    try:
        identity = {
            "scope": (meta.tenant_id, meta.workspace_id, meta.source_id),
            "raw_sha256": meta.raw_sha256,
            "filename": meta.filename,
            "kind": meta.kind,
            "loader": f"{type(loader).__module__}.{type(loader).__qualname__}",
            "implementation": inspect.getsource(type(loader)) + inspect.getsource(_pages_for),
            "configuration": vars(loader),
            "dependencies": _reader_dependencies(),
        }
        encoded = json.dumps(identity, sort_keys=True, allow_nan=False).encode()
    except (OSError, TypeError, ValueError):
        return None
    return "original-v2:" + hashlib.sha256(encoded).hexdigest()


def _pages_for(meta: SourceMeta, data: bytes, registry: LoaderRegistry) -> list[str]:
    """Page-structured text for a filing's original bytes.

    Every kind goes through its loader, so the RLM corpus reuses the ingest
    path's extraction -- in particular :class:`PdfLoader`'s Tesseract OCR
    fallback for scanned/image-only PDF pages, which the old bespoke fitz
    extraction missed. The loader's :class:`Section`\\ s are regrouped into
    the per-page list the engine cites into:

    * Paginated formats (PDF) emit one section per source page carrying a
      1-based ``page``; those are grouped by ``page`` (in first-seen order),
      each page's section bodies joined into one page string. PdfLoader emits
      exactly one section per non-empty page, so for text PDFs this is the
      same per-page text the old fitz path produced.
    * Non-paginated formats (docx / html / text ...) have ``page is None``;
      each such section stays its own page, preserving today's behaviour.

    Empty pages are skipped. With no usable sections we fall back to the
    loaded ``raw_text`` as a single page, else an empty list.
    """
    loader = registry.get(_source_kind(meta.kind))
    if loader is None:
        return []
    document = loader.load(data, filename=meta.filename)

    pages: list[str] = []
    by_page: dict[int, int] = {}  # 1-based page number -> index into ``pages``
    for section in document.sections:
        body = section.body
        if not (body and body.strip()):
            continue
        if section.page is None:
            pages.append(body)
            continue
        existing = by_page.get(section.page)
        if existing is None:
            by_page[section.page] = len(pages)
            pages.append(body)
        else:
            pages[existing] = f"{pages[existing]}\n{body}"
    if pages:
        return pages
    if document.raw_text and document.raw_text.strip():
        return [document.raw_text]
    return []


def _source_kind(kind: str) -> SourceKind:
    """Map a row's ``kind`` string to :class:`SourceKind`, defaulting to text."""
    try:
        return SourceKind(kind)
    except ValueError:
        return SourceKind.text


def _key_base(row: SourceRow) -> str:
    """Filename stem, falling back to title then source id."""
    if row.filename:
        stem = row.filename.rsplit("/", 1)[-1].rsplit(".", 1)[0].strip()
        if stem:
            return stem
    meta = row.metadata_json or {}
    title = meta.get("title") or (meta.get("extracted") or {}).get("title")
    if title and str(title).strip():
        return str(title).strip()
    return row.id


def _source_meta(row: SourceRow) -> SourceMeta:
    meta = row.metadata_json or {}
    title = meta.get("title") or (meta.get("extracted") or {}).get("title")
    original = meta.get("_persisted_original")
    original = original if isinstance(original, dict) else {}
    raw_sha = original.get("sha256")
    raw_bytes = original.get("bytes")
    verified_shape = (
        isinstance(raw_sha, str)
        and len(raw_sha) == 64
        and all(char in "0123456789abcdef" for char in raw_sha)
        and type(raw_bytes) is int
        and raw_bytes >= 0
    )
    return SourceMeta(
        source_id=row.id,
        filename=row.filename,
        title=str(title) if title else None,
        kind=row.kind,
        object_store_key=row.object_store_key or "",
        content_sha256=row.content_sha256,
        tenant_id=str(row.tenant_id),
        workspace_id=str(row.workspace_id),
        raw_sha256=raw_sha if verified_shape else None,
        raw_bytes=raw_bytes if verified_shape else None,
    )
