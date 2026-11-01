# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure citation mapping with distinct immutable document and curated identities."""

from flycanon.core.services.sources.lineage.dtos import DocumentCitationRef
from flycanon.interfaces.dtos.knowledge_corpus import KnowledgeCitationRef, KnowledgeVersionMeta
from flycanon.interfaces.dtos.query import Hit
from flycanon.interfaces.knowledge_corpus import RlmCorpus


def map_citations(cites: list[dict], docs: RlmCorpus) -> list[Hit]:
    """Turn engine citation dicts into hydrated :class:`Hit` rows.

    Each engine citation is ``{"filing": key, "page": int (0-based),
    "content": snippet}``. The readable ``filing`` key is resolved back to
    its source via :meth:`CanonDocStore.resolve`; citations whose key no
    longer resolves are dropped. Versioned documents use the actual immutable
    view part and recorded-loader page metadata. Standalone legacy documents
    retain their previous synthetic page mapping.
    """
    citations: list[Hit] = []
    for cite in cites:
        key = cite.get("filing")
        if not isinstance(key, str):
            continue
        meta = docs.resolve(key)
        if meta is None:
            continue
        content = cite.get("content", "")
        if isinstance(meta, KnowledgeVersionMeta):
            reference = docs.citation_ref(key, cite.get("page", 0), content)
            if not isinstance(reference, KnowledgeCitationRef):
                continue
            citations.append(
                Hit(
                    chunk_id=reference.part_id,
                    source_id=meta.native_item_id,
                    source_filename=None,
                    source_title=meta.title,
                    source_kind="knowledge_version",
                    knowledge_item_id=meta.native_item_id,
                    knowledge_version=meta.version,
                    page=None,
                    content=content,
                    score=1.0,
                    section_path=None,
                    metadata={
                        "knowledge_content_sha256": meta.content_sha256,
                        "knowledge_part_sha256": reference.part_sha256,
                    },
                )
            )
            continue
        if getattr(meta, "source_version_id", None) is not None:
            index = cite.get("page", 0)
            if type(index) is not int or not isinstance(content, str):
                continue
            reference = docs.citation_ref(key, index, content)
            if not isinstance(reference, DocumentCitationRef):
                continue
            page = None
            chunk_id = reference.part_id
            metadata = {
                "source_version_id": reference.source_version_id,
                "extraction_id": reference.extraction_id,
                "source_part_id": reference.part_id,
                "source_part_sha256": reference.sha256,
                "page_basis": reference.page_basis,
            }
            if reference.recorded_page is not None:
                metadata["recorded_page"] = str(reference.recorded_page)
        else:
            index = cite.get("page", 0)
            if type(index) is not int or not isinstance(content, str) or not content.strip():
                continue
            pages = docs.pages(key)
            if not 0 <= index < len(pages) or content not in pages[index]:
                continue
            page = index + 1
            chunk_id = f"{meta.source_id}#p{page}"
            metadata = {}
        citations.append(
            Hit(
                chunk_id=chunk_id,
                source_id=meta.source_id,
                source_filename=meta.filename,
                source_title=meta.title,
                source_kind=meta.kind,
                page=page,
                content=str(content),
                score=1.0,
                section_path=None,
                metadata=metadata,
            )
        )
    return citations
