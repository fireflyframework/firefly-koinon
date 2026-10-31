# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Request-local curated RLM evidence; never a cross-request corpus cache."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeVersionMeta, WholeKnowledgeRead

from koinon.knowledge.curated.corpus_dtos import ServingVersion


@dataclass(slots=True)
class CuratedRlmState:
    admissions: dict[tuple[str, str], ServingVersion] = field(default_factory=dict)
    metadata: dict[tuple[str, str], KnowledgeVersionMeta] = field(default_factory=dict)
    views: dict[tuple[str, str], WholeKnowledgeRead] = field(default_factory=dict)
    execution: dict[tuple[str, str], WholeKnowledgeRead] = field(default_factory=dict)
    authorizers: list[Callable[[], Awaitable[None]]] = field(default_factory=list)
