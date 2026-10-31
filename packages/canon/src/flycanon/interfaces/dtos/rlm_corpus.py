# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Corpus discovery metadata and filters, separate from query services."""

from collections.abc import Sequence
from dataclasses import dataclass


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
