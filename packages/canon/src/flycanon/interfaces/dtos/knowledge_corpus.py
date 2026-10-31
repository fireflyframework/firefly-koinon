# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Immutable approved-version inputs; part indices are not document pages."""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class KnowledgeVersionMeta:
    tenant_id: str
    workspace_id: str
    canonical_workspace_id: str
    item_id: str
    native_item_id: str
    version_id: str
    version: int
    operation_id: str
    title: str
    content_sha256: str
    evidence_sha256: str
    body_sha256: str
    body_chars: int
    body_bytes: int
    author_subject: str
    committed_at: str
    kind: Literal["knowledge_version"] = "knowledge_version"
    domain: str = "other"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class KnowledgeVersionPart:
    part_id: str
    ordinal: int
    char_start: int
    char_end: int
    sha256: str
    text: str = field(repr=False)


@dataclass(frozen=True, slots=True)
class KnowledgeReadContext:
    engine: str | None = None
    database: str | None = None
    catalog: str | None = None
    schema: str | None = None


@dataclass(frozen=True, slots=True)
class WholeKnowledgeRead:
    meta: KnowledgeVersionMeta
    parts: tuple[KnowledgeVersionPart, ...] = field(repr=False)
    manifest_sha256: str
    database: KnowledgeReadContext = field(default_factory=KnowledgeReadContext)

    @property
    def text(self) -> str:
        return "".join(part.text for part in self.parts)


@dataclass(frozen=True, slots=True)
class KnowledgeCitationRef:
    meta: KnowledgeVersionMeta
    part_id: str
    part_sha256: str
