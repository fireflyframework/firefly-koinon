# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass


@dataclass(frozen=True)
class Role:
    domain: str
    label: str
    purposes: tuple[str, ...]
    embedding: bool = False


ROLES = {
    "documents.answer": Role("documents", "Document answer and query expansion", ("search", "answer", "rlm")),
    "documents.fallback": Role("documents", "Explicit document answer fallback", ("answer",)),
    "documents.consolidation": Role("documents", "Document consolidation", ("ingest",)),
    "documents.rlm": Role("documents", "Document evidence tools", ("rlm",)),
    "documents.embedding": Role(
        "documents", "Document embeddings", ("ingest", "search", "answer", "rlm"), True
    ),
    "structured.grounding": Role("structured", "Structured question grounding", ("query",)),
    "structured.generation": Role("structured", "SQL generation", ("query",)),
    "structured.critic": Role("structured", "SQL repair", ("query",)),
    "structured.explainer": Role("structured", "Result explanation", ("query",)),
    "structured.describe": Role("structured", "Schema descriptions and names", ("ingest",)),
    "structured.relation_proposal": Role("structured", "Relation proposals", ("ingest",)),
    "structured.rename_detection": Role("structured", "Schema rename detection", ("ingest",)),
    "structured.embedding": Role("structured", "Structured schema embeddings", ("ingest", "query"), True),
}

PERMISSIONS = {
    "ingest": "ingest:write",
    "search": "knowledge:search",
    "answer": "knowledge:search",
    "rlm": "knowledge:search",
    "query": "query:execute",
}
