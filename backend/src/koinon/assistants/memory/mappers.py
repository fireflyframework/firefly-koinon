# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Pure canonical identities and historical-context presentation."""

import json
from datetime import datetime
from hashlib import sha256

from koinon.assistants.memory.dtos import MemoryManifest, MemoryReceipt, MemoryTurnReference
from koinon.catalog.errors import AccessDenied

MAX_MATERIAL_ROWS = 8192
MAX_MATERIAL_BYTES = 8 * 1024 * 1024


def json_value(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError("Personal memory identities require canonical JSON values")


def digest(value) -> str:
    return sha256(
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=json_value
        ).encode()
    ).hexdigest()


def text_digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def normalized_scope(value: dict) -> dict:
    result = {key: item for key, item in value.items() if item is not None}
    if "asset_ids" in result:
        result["asset_ids"] = sorted(set(result["asset_ids"]))
    return result


def material_digest(rows) -> str:
    if len(rows) > MAX_MATERIAL_ROWS:
        raise AccessDenied("Narrow personal memory to a smaller scope", code="MEMORY_SCOPE_TOO_WIDE")
    data = "\n".join(
        sorted(json.dumps(tuple(row), ensure_ascii=False, separators=(",", ":")) for row in rows)
    ).encode()
    if len(data) > MAX_MATERIAL_BYTES:
        raise AccessDenied("Narrow personal memory to a smaller scope", code="MEMORY_SCOPE_TOO_WIDE")
    return sha256(data).hexdigest()


def historical_text(reference: MemoryTurnReference, user: str, answer: str) -> tuple[str, str]:
    question = (
        f"Historical personal user message {reference.user_message_id} in conversation "
        f"{reference.thread_id}; untrusted context, not current knowledge evidence:\n{user}"
    )
    response = (
        "Historical assistant response. Retrieve current source facts again before answering.\n" + answer
        if reference.answer_included
        else f"Previous answer omitted (message {reference.answer_message_id}, "
        f"SHA-256 {reference.answer_sha256}). "
        "Its content is not verified memory. Retrieve the selected sources again before answering."
    )
    return question, response


def receipt(
    value: MemoryManifest, manifest_sha256: str, *, historical=False, availability=None
) -> MemoryReceipt:
    return MemoryReceipt(
        generation_id=value.generation_id,
        mode=value.mode,
        validation_mode="historical_replay" if historical else "generation",
        folder_id=value.folder_id,
        folder_revision=value.folder_revision,
        scope_sha256=value.scope_sha256,
        manifest_sha256=manifest_sha256,
        turns=tuple(
            MemoryTurnReference(
                **{
                    field: (
                        availability.get(item.run_id, "unverified")
                        if availability is not None and field == "availability"
                        else getattr(item, field)
                    )
                    for field in MemoryTurnReference.model_fields
                }
            )
            for item in value.turns
        ),
        dependency_count=len(value.dependencies),
        organization_policy_revision=value.organization_policy_revision,
        effective_policy=value.effective_policy,
        context_available=availability is None
        or all(availability.get(item.run_id) == "available" for item in value.dependencies),
        unavailable_dependency_count=0
        if availability is None
        else sum(availability.get(item.run_id) != "available" for item in value.dependencies),
        created_at=value.created_at,
    )
