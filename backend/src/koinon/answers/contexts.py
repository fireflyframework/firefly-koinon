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
