# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Admit exact whole-view parts before RLM code receives their bytes."""

from hashlib import sha256
from threading import get_ident

from flycanon.core.services.query import provenance
from flycanon.core.services.sources.lineage.dtos import WholeDocumentRead
from pyfly.kernel import ServiceUnavailableException

from koinon.knowledge.capture_dtos import DocumentRead, NativeDatabaseContext, NativeReadFingerprint

_MODELS = frozenset({"rlm.root", "rlm.submodel", "rlm.forced_final", "rlm.selector"})
EXECUTION_READ = "rlm.execution_read.v1"


def unavailable():
    return ServiceUnavailableException(
        "Exact recorded RLM document provenance is unavailable", code="EVIDENCE_UNAVAILABLE"
    )


def _identifier(value):
    return isinstance(value, str) and 0 < len(value) <= 64


def _sha(value):
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _page(value):
    if value is None:
        return None
    if isinstance(value, str) and len(value) <= 10 and value.isascii() and value.isdecimal():
        value = int(value)
    if type(value) is not int or not 1 <= value <= 2147483647:
        raise unavailable()
    return value


def tool_scope(receipt, scope):
    if (scope is None or provenance.current() is not scope or not scope.active or receipt.closed
            or scope.observer is not receipt or scope.task is not receipt.owner
            or scope.task.done() or scope.task.cancelling() or scope.loop.is_closed()
            or get_ident() not in scope.threads or scope.tenant_id != receipt.tenant_id
            or scope.actor != receipt.subject or not scope.source_ids
            or any((scope.workspace_id, source) not in receipt.canonical_documents
                   or scope.allowed_sources is not None and source not in scope.allowed_sources
                   for source in scope.source_ids)):
        raise unavailable()


def document_view_parts(receipt, meta, read, scope):
    if (
        provenance.current() is not scope
        or scope is None
        or not scope.active
        or receipt.closed
        or scope.observer is not receipt
        or scope.task is not receipt.owner
        or scope.task.done()
        or scope.task.cancelling()
        or get_ident() not in scope.threads
        or scope.loop.is_closed()
        or scope.tenant_id != receipt.tenant_id
        or scope.actor != receipt.subject
        or (meta.tenant_id, meta.workspace_id) != (scope.tenant_id, scope.workspace_id)
        or not isinstance(read, WholeDocumentRead)
        or not all(
            _identifier(value)
            for value in (
                meta.source_id,
                meta.source_version_id,
                meta.ingestion_extraction_id,
                read.extraction_id,
                read.input_artifact_id,
                read.normalized_artifact_id,
            )
        )
        or (read.source_id, read.source_version_id, read.ingestion_extraction_id)
        != (meta.source_id, meta.source_version_id, meta.ingestion_extraction_id)
        or (read.raw_sha256, read.normalized_sha256) != (meta.raw_sha256, meta.content_sha256)
        or not all(_sha(value) for value in (read.raw_sha256, read.normalized_sha256, read.input_sha256))
        or scope.allowed_sources is not None
        and meta.source_id not in scope.allowed_sources
        or (scope.workspace_id, meta.source_id) not in receipt.canonical_documents
    ):
        raise unavailable()
    provenance.authority(scope)
    if (
        not read.pages
        or sha256("\n".join(page.text for page in read.pages).encode()).hexdigest() != read.input_sha256
    ):
        raise unavailable()
    pending = []
    identifiers = set()
    for page in read.pages:
        if (
            not _identifier(page.part_id)
            or page.part_id in identifiers
            or not isinstance(page.text, str)
            or not page.text
            or not _sha(page.sha256)
            or sha256(page.text.encode()).hexdigest() != page.sha256
            or page.page_basis != "recorded_loader"
            or not page.source_sections
            or any(
                not _identifier(identifier) or not _sha(digest) for identifier, digest in page.source_sections
            )
        ):
            raise unavailable()
        identifiers.add(page.part_id)
        quote = page.text[:8000]
        value = DocumentRead(
            scope.workspace_id,
            read.source_id,
            page.part_id,
            sha256(quote.encode()).hexdigest(),
            quote,
            None,
            None,
            read.source_version_id,
            read.extraction_id,
            page.part_id,
            page.sha256,
            _page(page.page),
        )
        previous = receipt.documents.get(page.part_id)
        if previous is not None and previous != value:
            raise unavailable()
        pending.append(value)
    key = (scope.workspace_id, read.source_id)
    views = getattr(receipt, "_rlm_document_views", {})
    if key in views and views[key] != read:
        raise unavailable()
    database = receipt.source_contexts.get(read.source_id, NativeDatabaseContext())
    following_read = NativeReadFingerprint(
        "rlm.read",
        "canon",
        scope.tenant_id,
        scope.workspace_id,
        read.source_id,
        read.input_sha256,
        (read.source_id,),
        (),
        engine=database.engine,
        database=database.database,
        catalog=database.catalog,
        schema=database.schema,
        read_kind="document_extraction",
        origin=receipt.source_origins.get(read.source_id),
        source_version_id=read.source_version_id,
        extraction_id=read.extraction_id,
    )
    receipt.budget.check(receipt, documents=pending, reads=[following_read])
    receipt.document_extraction(read.source_id, read.source_version_id, read.extraction_id, scope)
    receipt.documents.update({row.chunk_id: row for row in pending})
    receipt._rlm_document_views = {**views, key: read}


def document_execution_read(receipt, meta, read, scope):
    """Record invocation-scoped code input, never inferred from hydration or model metadata."""
    key = (scope.workspace_id, meta.source_id) if scope is not None else None
    if (
        provenance.current() is not scope
        or scope is None
        or not scope.active
        or receipt.closed
        or scope.observer is not receipt
        or scope.task is not receipt.owner
        or scope.task.done()
        or scope.task.cancelling()
        or get_ident() not in scope.threads
        or scope.loop.is_closed()
        or scope.tenant_id != receipt.tenant_id
        or scope.actor != receipt.subject
        or (meta.tenant_id, meta.workspace_id) != (scope.tenant_id, scope.workspace_id)
        or not isinstance(read, WholeDocumentRead)
        or getattr(receipt, "_rlm_document_views", {}).get(key) != read
        or (read.source_id, read.source_version_id, read.ingestion_extraction_id)
        != (meta.source_id, meta.source_version_id, meta.ingestion_extraction_id)
        or scope.allowed_sources is not None and meta.source_id not in scope.allowed_sources
        or key not in receipt.canonical_documents
    ):
        raise unavailable()
    provenance.authority(scope)
    database = receipt.source_contexts.get(read.source_id, NativeDatabaseContext())
    following = NativeReadFingerprint(
        EXECUTION_READ, "canon", scope.tenant_id, scope.workspace_id, read.source_id,
        read.input_sha256, (read.source_id,), (), engine=database.engine, database=database.database,
        catalog=database.catalog, schema=database.schema, read_kind="document_extraction",
        origin=receipt.source_origins.get(read.source_id), source_version_id=read.source_version_id,
        extraction_id=read.extraction_id,
    )
    receipt.budget.check(receipt, reads=[following])
    receipt.native_reads.append(following)
    receipt._rlm_execution_views = {**getattr(receipt, "_rlm_execution_views", {}), key: read}


def execution_views(receipt):
    registered = getattr(receipt, "_rlm_execution_views", {})
    observed = set()
    for row in receipt.native_reads:
        key = (row.workspace_id, row.entity_id)
        view = registered.get(key)
        if (
            row.stage == EXECUTION_READ and view is not None
            and getattr(receipt, "_rlm_document_views", {}).get(key) == view
            and row.domain == "canon" and row.tenant_id == receipt.tenant_id
            and row.source_ids == (view.source_id,)
            and (row.read_kind, row.source_version_id, row.extraction_id, row.content_sha256)
            == ("document_extraction", view.source_version_id, view.extraction_id, view.input_sha256)
        ):
            observed.add(key)
    return frozenset(observed)


def _citation_field(citation, name):
    metadata = citation.get("metadata") or {}
    nested, direct = metadata.get(name), citation.get(name)
    if nested is not None and direct is not None and nested != direct:
        raise unavailable()
    return nested if nested is not None else direct


def verified_rlm_answer(receipt, data, admitted):
    views = getattr(receipt, "_rlm_document_views", {})
    if not views or not isinstance(data.get("answer"), str) or not data["answer"].strip():
        return False
    parts = {page.part_id: (key, view, page) for key, view in views.items() for page in view.pages}
    if set(parts) != set(receipt.documents):
        return False
    reads, models, released = set(), set(), set()
    for row in receipt.native_reads:
        if not row.stage.startswith("rlm.") or row.tenant_id != receipt.tenant_id or row.domain != "canon":
            return False
        for source in row.source_ids:
            key = (row.workspace_id, source)
            if key not in admitted or row.entity_id != source:
                raise unavailable()
            if row.stage in {"rlm.read", EXECUTION_READ}:
                view = views.get(key)
                if view is None or (
                    row.read_kind,
                    row.source_version_id,
                    row.extraction_id,
                    row.content_sha256,
                ) != ("document_extraction", view.source_version_id, view.extraction_id, view.input_sha256):
                    raise unavailable()
                (released if row.stage == EXECUTION_READ else reads).add(key)
            elif row.stage in _MODELS:
                if row.extraction_id is not None or row.source_version_id is not None:
                    view = views.get(key)
                    if view is None or (row.read_kind, row.source_version_id, row.extraction_id) != (
                        "document_extraction",
                        view.source_version_id,
                        view.extraction_id,
                    ):
                        raise unavailable()
                if row.stage in {"rlm.root", "rlm.forced_final"}:
                    # Corpus admission to a request is separate from successful execution input below.
                    models.add(key)
            elif row.stage != "rlm.corpus" or row.read_kind != "metadata":
                return False
    if set(views) - reads or set(views) - models or released != execution_views(receipt):
        return False
    citations = data.get("citations")
    if not isinstance(citations, list) or not citations:
        return False
    used_citations = True
    for citation in citations:
        if not isinstance(citation, dict):
            raise unavailable()
        part_id = _citation_field(citation, "source_part_id")
        found = parts.get(part_id)
        if found is None:
            raise unavailable()
        key, view, page = found
        used_citations = used_citations and key in released
        chain, binding = admitted[key]
        if (
            (binding.native_workspace_id, binding.native_id) != key
            or (citation.get("asset_id"), citation.get("source_id")) != (chain[0].id, chain[1].id)
            or citation.get("chunk_id") not in (None, part_id)
            or (
                _citation_field(citation, "source_version_id"),
                _citation_field(citation, "extraction_id"),
                _citation_field(citation, "source_part_sha256"),
                _citation_field(citation, "page_basis"),
            )
            != (view.source_version_id, view.extraction_id, page.sha256, "recorded_loader")
            or _page(_citation_field(citation, "recorded_page")) != page.page
            or not isinstance(citation.get("content"), str)
            or not citation["content"]
            or citation["content"] not in page.text
        ):
            raise unavailable()
    return used_citations
