# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bound immutable payload SQL before fetching text or JSON projection bytes."""

from hashlib import sha256

from pyfly.kernel import InvalidRequestException, ServiceUnavailableException
from sqlalchemy import LargeBinary, Text, and_, cast, func, select, tuple_

from flycanon.models.entities.source_lineage import (
    source_artifacts,
    source_events,
    source_extractions,
    source_parts,
    source_versions,
)
from flycanon.models.repositories.lineage.statements import conditions


def _unavailable(message):
    raise ServiceUnavailableException(message, code="DOCUMENT_PART_UNAVAILABLE")


def _related(left, right, identifier, *, extraction=False):
    predicates = [right.c.id == identifier]
    predicates.extend(left.c[key] == right.c[key] for key in ("tenant_id", "workspace_id", "source_id"))
    if extraction:
        predicates.append(left.c.extraction_id == right.c.extraction_id)
    return and_(*predicates)


def _byte_length(column, dialect):
    value = func.length(cast(column, LargeBinary)) if dialect == "sqlite" else func.octet_length(column)
    return func.coalesce(value, 0)


def _part_key(row, identifier="id"):
    return tuple(row[key] for key in ("tenant_id", "workspace_id", "source_id", "extraction_id")) + (
        row[identifier],
    )


async def _payloads(session, table, identities, key_names, fields, dialect):
    if not identities:
        return {}
    columns = [table.c[name] for name in key_names]
    lengths = [
        _byte_length(
            cast(table.c[name], Text) if name in {"projection", "section_path"} else table.c[name], dialect
        )
        for name in fields
    ]
    rows = (
        (
            await session.execute(
                select(*columns, *(table.c[name] for name in fields))
                .where(tuple_(*columns, *lengths).in_([(*key, *sizes) for key, sizes in identities.items()]))
                .limit(len(identities) + 1)
            )
        )
        .mappings()
        .all()
    )
    result = {tuple(row[name] for name in key_names): row for row in rows}
    if len(rows) != len(identities) or set(result) != set(identities):
        _unavailable("The bounded immutable payload differs from its scoped metadata")
    return result


async def read_chunk_records(
    source_repository, scope, *predicates, max_rows=1000, max_bytes=64 * 1024 * 1024
):
    """Keep incomplete ledger chains visible so corruption cannot become legacy data."""
    if type(max_rows) is not int or not 1 <= max_rows <= 1000 or type(max_bytes) is not int or max_bytes < 1:
        raise InvalidRequestException("Select positive bounded immutable read limits", code="INVALID_PARTS")
    extraction = source_extractions
    version = source_versions
    raw = source_artifacts.alias("raw")
    normalized = source_artifacts.alias("normalized")
    parent = source_parts.alias("parent_section")
    committed = source_events.alias("committed_ingestion")
    async with source_repository.session() as session:
        dialect = session.get_bind().dialect.name
        query = (
            select(
                *(column for column in source_parts.c if column.name not in {"text", "section_path"}),
                _byte_length(source_parts.c.text, dialect).label("text_bytes"),
                _byte_length(cast(source_parts.c.section_path, Text), dialect).label("section_path_bytes"),
                extraction.c.id.label("bound_extraction_id"),
                extraction.c.version_id.label("source_version_id"),
                extraction.c.purpose,
                extraction.c.normalized_artifact_id,
                _byte_length(cast(extraction.c.projection, Text), dialect).label("projection_bytes"),
                committed.c.status.label("ingestion_status"),
                version.c.id.label("bound_version_id"),
                version.c.filename,
                parent.c.id.label("bound_parent_id"),
                parent.c.kind.label("parent_kind"),
                parent.c.artifact_id.label("parent_artifact_id"),
                _byte_length(parent.c.text, dialect).label("parent_text_bytes"),
                parent.c.sha256.label("parent_sha256"),
                *(
                    artifact.c[key].label(f"{prefix}_{key}")
                    for prefix, artifact in (("raw", raw), ("normalized", normalized))
                    for key in (
                        "id",
                        "role",
                        "sha256",
                        "bytes",
                        "object_key",
                        "media_type",
                        "object_reference_json",
                    )
                ),
            )
            .select_from(
                source_parts.outerjoin(
                    extraction, _related(source_parts, extraction, source_parts.c.extraction_id)
                )
                .outerjoin(version, _related(extraction, version, extraction.c.version_id))
                .outerjoin(raw, _related(version, raw, version.c.artifact_id))
                .outerjoin(normalized, _related(extraction, normalized, extraction.c.normalized_artifact_id))
                .outerjoin(parent, _related(source_parts, parent, source_parts.c.parent_id, extraction=True))
                .outerjoin(
                    committed,
                    and_(
                        committed.c.extraction_id == extraction.c.id,
                        committed.c.version_id == extraction.c.version_id,
                        committed.c.status == "committed",
                        *(
                            committed.c[key] == extraction.c[key]
                            for key in ("tenant_id", "workspace_id", "source_id")
                        ),
                    ),
                )
            )
            .where(*conditions(source_parts, scope), *predicates)
            .limit(max_rows + 1)
        )
        rows = [dict(row) for row in (await session.execute(query)).mappings().all()]
        if len(rows) > max_rows:
            _unavailable("The immutable ingestion metadata exceeds the bounded row limit")
        children, parents, extractions = {}, {}, {}
        for row in rows:
            key = _part_key(row)
            if key in children:
                _unavailable("The immutable ingestion binding is ambiguous")
            children[key] = (row["text_bytes"], row["section_path_bytes"])
            if row["bound_parent_id"] is not None:
                parents[_part_key(row, "bound_parent_id")] = (row["parent_text_bytes"],)
            if row["bound_extraction_id"] is not None:
                extractions[
                    tuple(row[name] for name in ("tenant_id", "workspace_id", "source_id"))
                    + (row["bound_extraction_id"],)
                ] = (row["projection_bytes"],)
        sizes = [
            size for group in (children, parents, extractions) for values in group.values() for size in values
        ]
        if any(type(size) is not int or size < 0 for size in sizes) or sum(sizes) > max_bytes:
            _unavailable("The selected immutable ingestion payloads exceed the verified read limit")
        part_names = ("tenant_id", "workspace_id", "source_id", "extraction_id", "id")
        child_values = await _payloads(
            session,
            source_parts,
            children,
            part_names,
            ("text", "section_path"),
            dialect,
        )
        parent_values = await _payloads(session, source_parts, parents, part_names, ("text",), dialect)
        projections = await _payloads(
            session,
            source_extractions,
            extractions,
            ("tenant_id", "workspace_id", "source_id", "id"),
            ("projection",),
            dialect,
        )
        parent_hashes = {
            key: sha256(value["text"].encode()).hexdigest() for key, value in parent_values.items()
        }
        for row in rows:
            child = child_values[_part_key(row)]
            parent_key = _part_key(row, "bound_parent_id")
            parent_value = parent_values.get(parent_key)
            extraction_key = tuple(row[name] for name in ("tenant_id", "workspace_id", "source_id")) + (
                row["bound_extraction_id"],
            )
            row.update(
                text=child["text"],
                section_path=child["section_path"],
                parent_text=parent_value["text"] if parent_value is not None else None,
                parent_content_sha256=parent_hashes.get(parent_key),
                projection=projections[extraction_key]["projection"]
                if extraction_key in projections
                else None,
            )
        return rows
