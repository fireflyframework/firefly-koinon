# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Deterministic Library labels from persisted, public catalog metadata."""

from sqlalchemy import and_, case, func, literal

from koinon.catalog.dtos import CatalogSummary

FORMATS = {
    "pdf": "application/pdf",
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
    "parquet": "application/vnd.apache.parquet",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "xls": "application/vnd.ms-excel",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "doc": "application/msword",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "html": "text/html",
    "md": "text/markdown",
    "txt": "text/plain",
    "xml": "application/xml",
    "yaml": "application/yaml",
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
}
FOLDERS = {"workspace", "project", "collection", "corpus", "source"}
LIBRARY_KINDS = FOLDERS | {"document", "dataset", "knowledge_item"}


def format_expression(entry):
    explicit = func.lower(func.trim(entry.metadata_json["format"].as_string()))
    mime = func.lower(func.trim(entry.metadata_json["media_type"].as_string()))
    return case(
        (explicit.in_(list(FORMATS)), explicit),
        *[(mime == value, literal(key)) for key, value in FORMATS.items()],
        *[
            (
                and_(
                    entry.kind.in_(["document", "dataset", "source"]), func.lower(entry.name).like(f"%.{key}")
                ),
                literal(key),
            )
            for key in FORMATS
        ],
        else_=None,
    )


def metadata_label(value):
    if isinstance(value, str):
        value = value.strip()
        if 0 < len(value) <= 64:
            return value
    return None


def recorded_number(metadata, *keys):
    for key in keys:
        value = metadata.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 9007199254740991:
            return value
    return None


def summary(entry, counts, file_format, source_metadata=None):
    metadata = entry.metadata_json or {}
    inherited = source_metadata or {}
    language = metadata_label(metadata.get("language"))
    language = language.lower() if language else None
    tags = [value for value in (file_format, language) if value]
    custom = metadata.get("tags")
    if isinstance(custom, list):
        tags.extend(label for value in custom if (label := metadata_label(value)))
    labels = {}
    for tag in tags:
        labels.setdefault(tag.lower(), tag)
    folder = entry.kind in FOLDERS
    size = recorded_number(metadata, "size_bytes", "bytes")
    if size is None and entry.kind == "document":
        size = recorded_number(inherited, "size_bytes", "bytes")
    return CatalogSummary.model_validate(
        {
            "child_count": counts.get("total", 0) if folder else None,
            "document_count": counts.get("document", 0) if folder else None,
            "dataset_count": counts.get("dataset", 0) if folder else None,
            "table_count": counts.get("table", 0) if entry.kind == "dataset" else None,
            "row_count": recorded_number(metadata, "row_count"),
            "column_count": recorded_number(metadata, "column_count"),
            "page_count": recorded_number(metadata, "page_count"),
            "size_bytes": size,
            "format": file_format,
            "language": language,
            "tags": list(labels.values()),
        }
    ).model_dump()
