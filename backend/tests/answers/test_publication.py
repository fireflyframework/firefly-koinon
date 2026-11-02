# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
import pytest

from koinon.answers.publication import descriptor, fragments, verified_fragments


def test_unicode_chunks_are_deterministic_contiguous_and_bound_to_the_sealed_policy():
    text = "Árbol 🧭 e\u0301\n" * 45
    chunks = fragments(text)
    policy = {"publication": descriptor(text)}
    assert len(chunks) > 1 and "".join(row["text"] for row in chunks) == text
    assert chunks[1]["text_offset"] == len(chunks[0]["text"].encode("utf-16-le")) // 2
    assert verified_fragments(text, policy) == chunks
    assert verified_fragments(text, {"publication": {**policy["publication"], "chunk_count": 1}}) is None
    assert verified_fragments(text + "unsealed", policy) is None
    assert verified_fragments(text, {"publication": {"format": "unknown"}}) is None
    assert verified_fragments(text, {}) is None


@pytest.mark.parametrize(
    "field,value", [("format", "raw-tokens"), ("chunk_size", 1), ("text_sha256", "0" * 64)]
)
def test_unsealed_metadata_cannot_select_or_change_the_publication_protocol(field, value):
    text = "Exact published text"
    assert verified_fragments(text, {"publication": {**descriptor(text), field: value}}) is None
