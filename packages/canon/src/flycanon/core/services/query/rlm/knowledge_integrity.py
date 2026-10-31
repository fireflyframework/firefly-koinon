# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Complete ordered body proof shared by corpus release and receipt admission."""

from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
from json import dumps
from uuid import NAMESPACE_URL, uuid5

from pyfly.kernel import ServiceUnavailableException

from flycanon.interfaces.dtos.knowledge_corpus import (
    KnowledgeReadContext,
    KnowledgeVersionMeta,
    KnowledgeVersionPart,
    WholeKnowledgeRead,
)

KNOWLEDGE_PART_CHARS = 4800
MAX_BODY_BYTES = 262144


def invalid() -> ServiceUnavailableException:
    return ServiceUnavailableException(
        "The approved version body failed complete projection validation",
        code="KNOWLEDGE_PROJECTION_INVALID",
    )


def validate_meta(meta: KnowledgeVersionMeta) -> None:
    if (
        type(meta) is not KnowledgeVersionMeta
        or meta.kind != "knowledge_version"
        or type(meta.version) is not int
        or not 1 <= meta.version <= 2147483647
        or any(
            type(value) is not str or not 0 < len(value) <= 64
            for value in (
                meta.tenant_id,
                meta.workspace_id,
                meta.canonical_workspace_id,
                meta.item_id,
                meta.native_item_id,
                meta.version_id,
                meta.operation_id,
            )
        )
        or type(meta.domain) is not str
        or not 0 < len(meta.domain) <= 64
        or type(meta.tags) is not tuple
        or len(meta.tags) > 64
        or any(type(tag) is not str or not 0 < len(tag) <= 128 for tag in meta.tags)
        or type(meta.title) is not str
        or not 0 < len(meta.title) <= 255
        or type(meta.author_subject) is not str
        or not 0 < len(meta.author_subject) <= 512
        or any(
            type(value) is not str
            or len(value) != 64
            or any(char not in "0123456789abcdef" for char in value)
            for value in (meta.content_sha256, meta.evidence_sha256, meta.body_sha256)
        )
    ):
        raise invalid()
    try:
        if type(meta.committed_at) is not str or len(meta.committed_at) > 64:
            raise ValueError("Missing committed timestamp")
        timestamp = datetime.fromisoformat(meta.committed_at)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("A committed timestamp must include its timezone")
    except ValueError:
        raise invalid() from None


def manifest_digest(meta: KnowledgeVersionMeta, parts: tuple[KnowledgeVersionPart, ...]) -> str:
    data = {
        "format": "koinon.knowledge.view.v1",
        "version": asdict(meta),
        "parts": [
            dict(
                id=part.part_id,
                ordinal=part.ordinal,
                char_start=part.char_start,
                char_end=part.char_end,
                sha256=part.sha256,
            )
            for part in parts
        ],
    }
    return sha256(
        dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


def complete_view(
    meta: KnowledgeVersionMeta,
    parts: tuple[KnowledgeVersionPart, ...],
    database: KnowledgeReadContext | None = None,
) -> WholeKnowledgeRead:
    validate_meta(meta)
    if (
        type(meta.body_chars) is not int
        or type(meta.body_bytes) is not int
        or not 0 < meta.body_chars <= MAX_BODY_BYTES
        or not 0 < meta.body_bytes <= MAX_BODY_BYTES
        or len(parts) != (meta.body_chars + KNOWLEDGE_PART_CHARS - 1) // KNOWLEDGE_PART_CHARS
        or len({part.part_id for part in parts}) != len(parts)
    ):
        raise invalid()
    for ordinal, part in enumerate(parts):
        start = ordinal * KNOWLEDGE_PART_CHARS
        end = min(start + KNOWLEDGE_PART_CHARS, meta.body_chars)
        if (
            type(part.ordinal) is not int
            or type(part.char_start) is not int
            or type(part.char_end) is not int
            or part.ordinal != ordinal
            or (part.char_start, part.char_end) != (start, end)
            or not isinstance(part.text, str)
            or len(part.text) != end - start
            or part.sha256 != sha256(part.text.encode()).hexdigest()
            or part.part_id != str(uuid5(NAMESPACE_URL, f"koinon:knowledge:{meta.version_id}:{ordinal}"))
        ):
            raise invalid()
    text = "".join(part.text for part in parts)
    if (
        len(text) != meta.body_chars
        or len(text.encode()) != meta.body_bytes
        or sha256(text.encode()).hexdigest() != meta.body_sha256
    ):
        raise invalid()
    return WholeKnowledgeRead(meta, parts, manifest_digest(meta, parts), database or KnowledgeReadContext())


def verify_view(value: WholeKnowledgeRead) -> None:
    if type(value) is not WholeKnowledgeRead:
        raise invalid()
    expected = complete_view(value.meta, value.parts, value.database)
    if expected != value:
        raise invalid()
