# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded discovery metadata; never document contents or execution instructions."""

import json


def metadata_index(entries, *, max_entries=32, max_bytes=16384) -> str:
    if type(max_entries) is not int or max_entries < 1 or type(max_bytes) is not int or max_bytes < 256:
        raise ValueError("Invalid corpus metadata limits")
    for entry in entries:
        if (
            set(entry) != {"filing_id", "filename", "title"}
            or not isinstance(entry["filing_id"], str) or not entry["filing_id"]
            or entry["filename"] is not None and not isinstance(entry["filename"], str)
            or entry["title"] is not None and not isinstance(entry["title"], str)
        ):
            raise ValueError("Only exact corpus identifiers and names are allowed")

    def render(selected):
        return json.dumps({
            "kind": "authorized_corpus_metadata", "schema_version": 1,
            "total_count": len(entries), "listed_count": len(selected),
            "partial": len(selected) < len(entries),
            "limits": {"entries": max_entries, "bytes": max_bytes}, "documents": selected,
        }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    selected = []
    for entry in entries[:max_entries]:
        candidate = [*selected, entry]
        if len(render(candidate).encode()) > max_bytes:
            break
        selected = candidate
    result = render(selected)
    if len(result.encode()) > max_bytes:
        raise ValueError("Corpus metadata envelope exceeds its limit")
    return result
