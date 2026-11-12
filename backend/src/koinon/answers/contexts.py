# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bind the private publication context without claiming a model call for a refusal."""

from koinon.answers.receipts import digest


def context_hash(release_sha256: str, reset_sequence: int) -> str:
    return digest({"release_sha256": release_sha256, "reset_sequence": reset_sequence})


def current_release_context(payload: dict, reset_sequence: int) -> bool:
    release = payload.get("release")
    recorded = payload.get("reset_sequence")
    sequence = release.get("publication_sequence") if isinstance(release, dict) else None
    seal = payload.get("seal_sha256")
    return (
        type(recorded) is int
        and recorded == reset_sequence
        and type(sequence) is int
        and sequence > reset_sequence
        and isinstance(seal, str)
        and payload.get("context_sha256") == context_hash(seal, recorded)
    )


def active_result_rows(rows, *, reset: int | None, run_id: str, artifacts):
    """Select persisted results with the original assistant history semantics."""
    rows = [
        row
        for row in rows
        if row.kind != "answer_release" or current_release_context(row.payload, reset or 0)
    ]
    if reset is None:
        return rows
    ids = {value["id"] for value in artifacts or [] if value.get("run_id") == run_id and value.get("id")}
    generations = [
        row
        for row in rows
        if row.kind == "generation" and row.payload["generation"]["start_sequence"] >= reset
    ]
    current = (
        max(generations, key=lambda row: (row.payload["generation"]["start_sequence"], row.created_at))
        if generations
        else None
    )
    return [
        row
        for row in rows
        if row.id in ids
        or row.kind == "answer_release"
        and row.payload.get("generation_id") is None
        or current is not None
        and (row.id == current.id or row.payload.get("generation_id") == current.id)
    ]
