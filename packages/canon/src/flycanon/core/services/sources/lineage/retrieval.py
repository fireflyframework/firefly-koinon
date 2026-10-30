# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bind actual retrieved text to its exact immutable ingestion part."""

from collections.abc import Sequence
from dataclasses import replace

from sqlalchemy import and_, select

from flycanon.core.services.retrieval.retrieval_service import Hit
from flycanon.core.services.sources.lineage.dtos import DocumentScope
from flycanon.core.services.sources.lineage.ingestion_parts import (
    _unavailable,
    chunk_records,
    validate_chunk,
)
from flycanon.core.services.sources.lineage.service import DocumentLineage, conditions
from flycanon.models.entities.source_lineage import source_events, source_extractions, source_parts

_IMMUTABLE_KEYS = frozenset(
    {
        "source_version_id",
        "extraction_id",
        "ingestion_extraction_id",
        "source_part_id",
        "source_part_sha256",
        "source_part_kind",
        "projection_chunk_id",
        "raw_artifact_id",
        "raw_sha256",
        "normalized_artifact_id",
        "normalized_sha256",
        "input_artifact_id",
        "input_sha256",
        "recorded_page",
        "page_basis",
    }
)


async def bind_retrieval_parts(
    lineage: DocumentLineage, scope: DocumentScope, hits: Sequence[Hit]
) -> list[Hit]:
    if not hits:
        return []
    await lineage.require_schema()
    rows = await chunk_records(
        lineage, scope, source_parts.c.projection_chunk_id.in_([h.chunk_id for h in hits])
    )
    async with lineage.sources.session() as session:
        versioned = set(
            (
                await session.scalars(
                    select(source_extractions.c.source_id)
                    .join(
                        source_events,
                        and_(
                            source_events.c.extraction_id == source_extractions.c.id,
                            source_events.c.version_id == source_extractions.c.version_id,
                            *(
                                source_events.c[key] == source_extractions.c[key]
                                for key in ("tenant_id", "workspace_id", "source_id")
                            ),
                        ),
                    )
                    .where(
                        *conditions(source_extractions, scope),
                        source_extractions.c.purpose == "ingestion",
                        source_extractions.c.source_id.in_([hit.source_id for hit in hits]),
                        source_events.c.status == "committed",
                    )
                )
            ).all()
        )
    parts = {}
    for row in rows:
        key = (row["source_id"], row["projection_chunk_id"])
        if key in parts:
            _unavailable("The immutable search projection is ambiguous")
        parts[key] = row
    enriched = []
    for hit in hits:
        metadata = {key: value for key, value in hit.metadata.items() if key not in _IMMUTABLE_KEYS}
        part = parts.get((hit.source_id, hit.chunk_id))
        if part is None and hit.source_id in versioned:
            _unavailable("The committed document has no exact immutable search projection")
        if part is not None:
            validate_chunk(part)
            if hit.content != part["text"]:
                _unavailable("The model-bound content differs from its immutable ingestion chunk")
            metadata.update(
                {
                    "source_version_id": part["source_version_id"],
                    "extraction_id": part["extraction_id"],
                    "ingestion_extraction_id": part["extraction_id"],
                    "source_part_id": part["id"],
                    "source_part_sha256": part["sha256"],
                    "source_part_kind": "chunk",
                    "page_basis": "recorded_loader",
                    "projection_chunk_id": hit.chunk_id,
                    "raw_artifact_id": part["raw_id"],
                    "raw_sha256": part["raw_sha256"],
                    "normalized_artifact_id": part["normalized_id"],
                    "normalized_sha256": part["normalized_sha256"],
                    "input_artifact_id": part["normalized_id"],
                    "input_sha256": part["normalized_sha256"],
                    "source_filename": part["filename"] or "",
                    "_observed_source_filename": part["filename"] or "",
                    "source_kind": part["projection"].get("kind", ""),
                }
            )
            metadata.pop("page", None)
            metadata.pop("section_path", None)
            metadata.pop("source_title", None)
            metadata.pop("source_uri", None)
            if part["page"] is not None:
                metadata["page"] = metadata["recorded_page"] = str(part["page"])
            if part["section_path"]:
                metadata["section_path"] = part["section_path"]
        enriched.append(replace(hit, metadata=metadata))
    return enriched
