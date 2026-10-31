# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Exact retained ingestion chunks, independent of the replaceable search projection."""

from hashlib import sha256

from pyfly.kernel import InvalidRequestException, ResourceNotFoundException, ServiceUnavailableException

from flycanon.core.services.sources.lineage.dtos import WholeDocumentPart
from flycanon.core.services.sources.lineage.ports import IngestionPartQuery


def _unavailable(message):
    raise ServiceUnavailableException(message, code="DOCUMENT_PART_UNAVAILABLE")


async def chunk_records(lineage, scope, *predicates, max_rows=1000, max_bytes=64 * 1024 * 1024):
    """Compatibility seam for retained callers with SQL predicates."""
    return await lineage.repository.legacy_chunks(scope, *predicates, max_rows=max_rows, max_bytes=max_bytes)


def validate_chunk(record):
    if (
        record["kind"] != "chunk"
        or record["purpose"] != "ingestion"
        or record["ingestion_status"] != "committed"
        or record["bound_extraction_id"] != record["extraction_id"]
        or record["bound_version_id"] != record["source_version_id"]
        or not record["bound_version_id"]
        or record["raw_role"] != "raw"
        or record["normalized_role"] != "normalized"
        or record["normalized_id"] != record["normalized_artifact_id"]
        or record["artifact_id"] != record["normalized_id"]
        or not record["projection_chunk_id"]
        or not isinstance(record["projection"], dict)
        or not isinstance(record["text"], str)
        or sha256(record["text"].encode()).hexdigest() != record["sha256"]
    ):
        _unavailable("The immutable ingestion chunk binding failed verification")
    if record["parent_id"] is not None and (
        record["bound_parent_id"] != record["parent_id"]
        or record["parent_kind"] != "section"
        or record["parent_artifact_id"] != record["normalized_id"]
        or record["parent_content_sha256"] != record["parent_sha256"]
    ):
        _unavailable("The immutable ingestion parent section failed verification")


async def read_exact_ingestion_chunk_parts(
    reader, scope, *, source_id, source_version_id, extraction_id, part_ids
):
    if not 1 <= len(part_ids) <= min(100, reader.max_parts) or len(set(part_ids)) != len(part_ids):
        raise InvalidRequestException("Select from1 to100 distinct immutable parts", code="INVALID_PARTS")
    lineage = reader.lineage
    await lineage.require_schema()
    rows = await lineage.repository.ingestion_chunks(
        scope,
        IngestionPartQuery(
            source_id=source_id,
            extraction_id=extraction_id,
            part_ids=tuple(part_ids),
            max_rows=min(1000, reader.max_parts),
            max_bytes=reader.max_bytes,
        ),
    )
    if len(rows) != len(part_ids) or any(
        row["source_version_id"] != source_version_id
        or row["purpose"] != "ingestion"
        or row["kind"] != "chunk"
        for row in rows
    ):
        raise ResourceNotFoundException(
            "The exact immutable ingestion chunks are unavailable", code="DOCUMENT_PART_NOT_FOUND"
        )
    for row in rows:
        validate_chunk(row)
    verified = set()
    for row in rows:
        for prefix in ("raw", "normalized"):
            artifact = {
                key: row[f"{prefix}_{key}"] for key in ("id", "sha256", "bytes", "object_key", "media_type")
            }
            if artifact["bytes"] > reader.max_bytes:
                _unavailable("The retained ingestion input exceeds the verified read limit")
            if artifact["id"] not in verified:
                await lineage._verified(artifact, reader.max_bytes)
                verified.add(artifact["id"])
    found = {
        row["id"]: WholeDocumentPart(
            row["id"],
            source_id,
            source_version_id,
            extraction_id,
            extraction_id,
            row["text"],
            row["sha256"],
            row["page"],
            "recorded_loader",
            ((row["parent_id"], row["parent_sha256"]),) if row["parent_id"] else (),
            row["raw_sha256"],
            row["normalized_sha256"],
            row["normalized_sha256"],
        )
        for row in rows
    }
    return tuple(found[identifier] for identifier in part_ids)
