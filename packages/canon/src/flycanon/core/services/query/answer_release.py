# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Extractive native answer compatibility: model conclusions are never source facts."""

from flycanon.interfaces.dtos.query import Hit

INSUFFICIENT_EVIDENCE = (
    "The selected knowledge does not contain enough verified source excerpts to release an answer."
)


def release_excerpts(citations: list[Hit], *, no_answer: bool = False) -> tuple[str, list[Hit], bool]:
    if no_answer or not citations or len(citations) > 16:
        return INSUFFICIENT_EVIDENCE, [], True
    if any(not hit.content.strip() or len(hit.content) > 8000 for hit in citations):
        return INSUFFICIENT_EVIDENCE, [], True
    text = "Source excerpts\n\n" + "\n\n".join(
        f"Source excerpt {index}:\n" + "\n".join("> " + line for line in hit.content.splitlines())
        for index, hit in enumerate(citations, 1)
    )
    if len(text.encode()) > 32768:
        return INSUFFICIENT_EVIDENCE, [], True
    return text, citations, False
