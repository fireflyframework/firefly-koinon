# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Public history record conversion without data access."""

from datetime import UTC

from pydantic import ValidationError
from pyfly.kernel import ServiceUnavailableException


def validated(model, values):
    try:
        return model.model_validate(values)
    except ValidationError as error:
        raise ServiceUnavailableException(
            "The recorded document history is incomplete", code="DOCUMENT_HISTORY_INVALID"
        ) from error


def timestamp(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def page_result(result, convert):
    return dict(
        items=tuple(convert(row) for row in result.items),
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        pages=result.pages,
        has_next=result.page * result.page_size < result.total,
        has_previous=result.page > 1,
    )


def version_record(row):
    return dict(
        source_version_id=row["id"],
        filename=row["filename"],
        media_type=row["media_type"],
        sha256=row["sha256"],
        byte_size=row["bytes"],
        actor=row["actor"],
        created_at=timestamp(row["created_at"]),
        predecessor_source_version_id=row["predecessor_id"],
    )


def extraction_record(row, artifact):
    return dict(
        source_version_id=row["version_id"],
        extraction_id=row["id"],
        purpose=row["purpose"],
        coverage=row["coverage"],
        normalized_sha256=artifact["sha256"],
        created_at=timestamp(row["created_at"]),
        predecessor_extraction_id=row["predecessor_id"],
    )


def part_record(row, version):
    return dict(
        source_version_id=version,
        extraction_id=row["extraction_id"],
        source_part_id=row["id"],
        kind=row["kind"],
        ordinal=row["ordinal"],
        sha256=row["sha256"],
        recorded_page=row["page"],
        page_basis="recorded_loader" if row["page"] is not None else None,
        char_start=row["char_start"],
        char_end=row["char_end"],
        offset_basis=row["offset_basis"],
        created_at=timestamp(row["created_at"]),
    )


def content_record(row, kind):
    return dict(
        source_version_id=row.source_version_id,
        extraction_id=row.extraction_id,
        source_part_id=row.part_id,
        kind=kind,
        sha256=row.sha256,
        text=row.text,
        recorded_page=row.page,
        page_basis=row.page_basis,
        raw_sha256=row.raw_sha256,
        normalized_sha256=row.normalized_sha256,
        input_sha256=row.input_sha256,
    )
