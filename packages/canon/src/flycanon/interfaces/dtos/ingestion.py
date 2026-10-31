# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed source-loading and chunking results."""

from dataclasses import dataclass

from flycanon.core.services.ingestion.loaders import Section
from flycanon.models.entities.knowledge_chunk import KnowledgeChunkRow
from flycanon.models.entities.source import SourceRow


@dataclass(slots=True)
class IngestionResult:
    """The output of one ingestion call.

    ``chunks`` is fresh on every call -- callers persist them through
    :class:`ChunkRepository`. The ``source`` row is mutated in place
    so callers can refresh status / counters in their own session.
    """

    source: SourceRow
    chunks: list[KnowledgeChunkRow]
    sections: tuple[Section, ...] = ()
    chunk_section_indices: tuple[int | None, ...] = ()
