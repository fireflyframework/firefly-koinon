# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure approved-version and native-part mappings; no database or inference calls."""

from hashlib import sha256
from typing import TYPE_CHECKING

from flycanon.core.services.query.rlm.knowledge_integrity import complete_view, invalid, manifest_digest
from flycanon.core.services.retrieval.retrieval_service import Hit
from flycanon.interfaces.dtos.knowledge_corpus import (
    KnowledgeReadContext,
    KnowledgeVersionMeta,
    KnowledgeVersionPart,
    WholeKnowledgeRead,
)
from pyfly.kernel import ConflictException

from koinon.knowledge.capture_dtos import NativeDatabaseContext
from koinon.knowledge.curated.authority import digest
from koinon.knowledge.curated.corpus_dtos import CuratedPartRecord, ServingVersion
from koinon.knowledge.curated.dtos import KnowledgeItemView, KnowledgeVersionView

if TYPE_CHECKING:
    from flycanon.models.entities.knowledge_version import KnowledgeVersionRow

    from koinon.knowledge.curated.domain_entities import CuratedVersionChunkRow


__all__ = ["manifest_digest", "version_meta", "whole_view"]


def version_meta(
    value: KnowledgeItemView, selected: ServingVersion, *, tenant_id: str, native_workspace_id: str
) -> KnowledgeVersionMeta:
    version = value.selected_version
    if (
        value.tenant_id,
        value.workspace_id,
        value.id,
        version.item_id,
        version.version_id,
        version.version,
        value.serving_version,
        version.publication,
        version.serving,
        selected.native_workspace_id,
    ) != (
        tenant_id,
        selected.workspace_id,
        selected.item_id,
        selected.item_id,
        selected.version_id,
        selected.version,
        selected.version,
        "published",
        True,
        native_workspace_id,
    ):
        raise ConflictException(
            "The acknowledged published version changed", code="KNOWLEDGE_VERSION_CONFLICT"
        )
    body = version.content.body
    if version.content_sha256 != digest(
        version.content.model_dump(mode="json")
    ) or version.evidence_sha256 != digest([v.model_dump(mode="json") for v in version.evidence]):
        raise invalid()
    return KnowledgeVersionMeta(
        tenant_id=tenant_id,
        workspace_id=native_workspace_id,
        canonical_workspace_id=value.workspace_id,
        item_id=value.id,
        native_item_id=selected.native_item_id,
        version_id=version.version_id,
        version=version.version,
        operation_id=version.operation_id,
        title=version.content.title,
        content_sha256=version.content_sha256,
        evidence_sha256=version.evidence_sha256,
        body_sha256=sha256(body.encode()).hexdigest(),
        body_chars=len(body),
        body_bytes=len(body.encode()),
        author_subject=version.author_subject,
        committed_at=version.committed_at.isoformat(),
        domain=version.content.domain,
        tags=version.content.tags,
    )


def whole_view(
    meta: KnowledgeVersionMeta,
    body: str,
    parts: tuple[CuratedPartRecord, ...],
    database: NativeDatabaseContext | None = None,
) -> WholeKnowledgeRead:
    if sha256(body.encode()).hexdigest() != meta.body_sha256:
        raise invalid()
    for part in parts:
        if (
            part.tenant_id,
            part.workspace_id,
            part.canonical_item_id,
            part.native_item_id,
            part.native_version_id,
        ) != (
            meta.tenant_id,
            meta.workspace_id,
            meta.item_id,
            meta.native_item_id,
            meta.version_id,
        ) or part.content != body[part.char_start : part.char_end]:
            raise invalid()
    projected = tuple(
        KnowledgeVersionPart(part.id, part.ordinal, part.char_start, part.char_end, part.sha256, part.content)
        for part in parts
    )
    context = database or NativeDatabaseContext()
    return complete_view(
        meta,
        projected,
        KnowledgeReadContext(context.engine, context.database, context.catalog, context.schema),
    )


def part_record(value: "CuratedVersionChunkRow", native_item_id: str) -> CuratedPartRecord:
    return CuratedPartRecord(
        value.id,
        value.tenant_id,
        value.workspace_id,
        value.canonical_item_id,
        native_item_id,
        value.native_version_id,
        value.ordinal,
        value.content,
        value.sha256,
        value.char_start,
        value.char_end,
    )


def lexical_hit(
    part: "CuratedVersionChunkRow",
    native_version: "KnowledgeVersionRow",
    selected: ServingVersion,
    receipt: KnowledgeVersionView,
    ordinal: int,
) -> Hit:
    body = receipt.content
    if (
        part.canonical_item_id != selected.item_id
        or native_version.knowledge_item_id != selected.native_item_id
        or part.content != body.body[part.char_start : part.char_end]
        or part.sha256 != sha256(part.content.encode()).hexdigest()
    ):
        raise invalid()
    return Hit(
        chunk_id=part.id,
        source_id=selected.native_item_id,
        knowledge_item_id=selected.native_item_id,
        knowledge_version=selected.version,
        content=part.content,
        score=1 / (60 + ordinal),
        bm25_rank=None,
        vector_rank=None,
        metadata={
            "source_kind": "knowledge_version",
            "source_title": body.title,
            "knowledge_version_id": selected.version_id,
            "knowledge_content_sha256": receipt.content_sha256,
            "canonical_knowledge_item_id": selected.item_id,
            "_knowledge_status": "published",
            "_knowledge_domain": body.domain,
            "_knowledge_tags": ",".join(body.tags),
        },
    )
