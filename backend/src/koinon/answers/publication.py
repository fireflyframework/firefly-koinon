# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Deterministic fragments of an already sealed answer, never model token output."""

from hashlib import sha256

from pydantic import ValidationError

from koinon.answers.publication_dtos import AnswerPublication

_CHUNK_SIZE = 128


def descriptor(text: str) -> dict:
    return AnswerPublication(
        format="verified-unicode-v1",
        chunk_size=_CHUNK_SIZE,
        chunk_count=max(1, (len(text) + _CHUNK_SIZE - 1) // _CHUNK_SIZE),
        text_sha256=sha256(text.encode()).hexdigest(),
    ).model_dump()


def fragments(text: str) -> tuple[dict, ...]:
    count = max(1, (len(text) + _CHUNK_SIZE - 1) // _CHUNK_SIZE)
    offset = 0
    result = []
    for index in range(count):
        chunk = text[index * _CHUNK_SIZE : (index + 1) * _CHUNK_SIZE]
        result.append({"text": chunk, "chunk_index": index, "chunk_count": count, "text_offset": offset})
        offset += len(chunk.encode("utf-16-le")) // 2
    return tuple(result)


def verified_fragments(text: str, policy: dict) -> tuple[dict, ...] | None:
    try:
        recorded = AnswerPublication.model_validate(policy.get("publication"))
        if recorded.model_dump() != descriptor(text):
            return None
        return fragments(text)
    except (ValidationError, ValueError, TypeError):
        return None
