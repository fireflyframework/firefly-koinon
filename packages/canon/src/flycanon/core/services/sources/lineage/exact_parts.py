# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Resolve historical page parts without replaying a current extraction algorithm."""

from __future__ import annotations

from hashlib import sha256
from typing import TYPE_CHECKING

from pyfly.kernel import InvalidRequestException, ResourceNotFoundException

from flycanon.core.services.sources.lineage.dtos import DocumentScope, WholeDocumentPart
from flycanon.core.services.sources.lineage.ports import LineageQuery

if TYPE_CHECKING:
    from flycanon.core.services.sources.lineage.whole_read import WholeDocumentReader


async def read_exact_parts(
    reader: WholeDocumentReader,
    scope: DocumentScope,
    *,
    source_id: str,
    source_version_id: str,
    extraction_id: str,
    part_ids: tuple[str, ...],
) -> tuple[WholeDocumentPart, ...]:
    if not 1 <= len(part_ids) <= 100 or len(set(part_ids)) != len(part_ids):
        raise InvalidRequestException("Select from1 to100 distinct immutable parts", code="INVALID_PARTS")
    lineage = reader.lineage
    await lineage.require_schema()
    async with lineage.repository.read() as session:
        extraction = await session.first(
            LineageQuery(
                "extraction",
                scope,
                source_id=source_id,
                equal={
                    "id": extraction_id,
                    "version_id": source_version_id,
                    "purpose": "whole_document_read",
                },
            )
        )
        requested = await session.all(
            LineageQuery(
                "part",
                scope,
                source_id=source_id,
                equal={"extraction_id": extraction_id, "kind": "page"},
                included={"id": part_ids},
            )
        )
        if extraction is None or len(requested) != len(part_ids):
            raise ResourceNotFoundException(
                "The exact immutable document parts are unavailable", code="DOCUMENT_PART_NOT_FOUND"
            )
        projection = extraction["projection"]
        if (
            projection.get("view_representation") != "utf8_pages_joined_newline.v1"
            or projection.get("page_basis") != "recorded_loader"
        ):
            reader._unavailable("This historical document view has an unsupported recorded representation")
        ingestion = await session.first(
            LineageQuery(
                "extraction",
                scope,
                source_id=source_id,
                equal={
                    "id": projection.get("input_extraction_id"),
                    "version_id": source_version_id,
                    "purpose": "ingestion",
                },
            )
        )
        if ingestion is None or ingestion["normalized_artifact_id"] != extraction["normalized_artifact_id"]:
            reader._unavailable("The immutable input extraction binding is unavailable")
        normalized = await session.first(
            LineageQuery(
                "artifact",
                scope,
                source_id=source_id,
                equal={"id": extraction["normalized_artifact_id"], "role": "normalized"},
            )
        )
        output = await session.first(
            LineageQuery(
                "artifact",
                scope,
                source_id=source_id,
                equal={"id": projection.get("output_artifact_id"), "role": "whole_document_view"},
            )
        )
        pages = await session.all(
            LineageQuery(
                "part",
                scope,
                source_id=source_id,
                order=("ordinal",),
                limit=reader.max_parts + 1,
                equal={"extraction_id": extraction_id, "kind": "page"},
            )
        )
        sections = await session.all(
            LineageQuery(
                "part",
                scope,
                source_id=source_id,
                limit=reader.max_parts + 1,
                equal={"extraction_id": ingestion["id"], "kind": "section"},
            )
        )
    if (
        normalized is None
        or output is None
        or not pages
        or not sections
        or max(len(pages), len(sections)) > reader.max_parts
    ):
        reader._unavailable("The complete historical document input and view are required")
    if max(normalized["bytes"], output["bytes"]) > reader.max_bytes:
        reader._unavailable("The historical document view exceeds the verified read limit")
    version = await lineage.version(scope, source_id, source_version_id)
    if version["bytes"] > reader.max_bytes:
        reader._unavailable("The historical original exceeds the verified read limit")
    await lineage.original(scope, source_id, source_version_id, max_bytes=reader.max_bytes)
    await lineage._verified(normalized, reader.max_bytes)
    view = await lineage._verified(output, reader.max_bytes)
    if sum(len(page["text"].encode()) for page in pages) > reader.max_bytes:
        reader._unavailable("The historical document text exceeds the verified read limit")
    expected = "\n".join(page["text"] for page in pages).encode()
    if len(expected) > reader.max_bytes or view != expected:
        reader._unavailable("The exact historical view failed integrity verification")
    parents = {section["id"]: section for section in sections}
    parent_lists = projection.get("section_ids_by_page")
    digests = projection.get("source_section_digests", {})
    if not isinstance(parent_lists, list) or len(parent_lists) != len(pages):
        reader._unavailable("The complete historical section manifest is unavailable")
    flattened = []
    found = {}
    for ordinal, (page, identifiers) in enumerate(zip(pages, parent_lists, strict=True)):
        if (
            page["ordinal"] != ordinal
            or page["artifact_id"] != output["id"]
            or page["sha256"] != sha256(page["text"].encode()).hexdigest()
            or not isinstance(identifiers, list)
            or not identifiers
        ):
            reader._unavailable("The exact historical page manifest is incompatible")
        for identifier in identifiers:
            parent = parents.get(identifier)
            if (
                parent is None
                or parent["artifact_id"] != normalized["id"]
                or parent["sha256"] != sha256(parent["text"].encode()).hexdigest()
                or digests.get(identifier) != parent["sha256"]
            ):
                reader._unavailable("The immutable parent section binding failed verification")
        flattened.extend(identifiers)
        found[page["id"]] = WholeDocumentPart(
            page["id"],
            source_id,
            source_version_id,
            extraction_id,
            ingestion["id"],
            page["text"],
            page["sha256"],
            page["page"],
            "recorded_loader",
            tuple((identifier, parents[identifier]["sha256"]) for identifier in identifiers),
            version["sha256"],
            normalized["sha256"],
            output["sha256"],
        )
    expected_parents = {identifier for identifier, part in parents.items() if part["text"].strip()}
    if len(flattened) != len(set(flattened)) or set(flattened) != expected_parents:
        reader._unavailable("The recorded view does not cover its complete committed input sections")
    return tuple(found[identifier] for identifier in part_ids)
