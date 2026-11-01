# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Read-only validation of an immutable server-published answer binding."""

import json
from collections.abc import Sequence
from hashlib import sha256
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, ValidationError

from koinon.assistants.entities import ChatMessage, ToolResult
from koinon.evidence.dtos import SourceReference


class ResultPin(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str = Field(min_length=1, max_length=64)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class AnswerRelease(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1] = 1
    policy_version: Literal["knowledge-only-v1"] = "knowledge-only-v1"
    run_id: str = Field(min_length=1, max_length=64)
    message_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    generation_id: str | None = None
    publication_sequence: int = Field(ge=1)
    outcome: Literal["grounded", "refused", "review_required"]
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    citations_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    artifacts_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fact_ids: tuple[str, ...] = Field(default=(), max_length=80)
    result_pins: tuple[ResultPin, ...] = Field(default=(), max_length=100)
    source_refs: tuple[SourceReference, ...] = Field(default=(), max_length=500)
    created_at: AwareDatetime


def digest(value: object) -> str:
    return sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    ).hexdigest()


def text_digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


def verified_release(message: ChatMessage, rows: Sequence[ToolResult]) -> AnswerRelease | None:
    index = {row.id: row for row in rows}
    generations = [row for row in rows if row.kind == "generation"]
    current = (
        max(generations, key=lambda row: (row.payload["generation"]["start_sequence"], row.created_at)).id
        if generations
        else None
    )
    for row in rows:
        if row.kind != "answer_release":
            continue
        try:
            receipt = AnswerRelease.model_validate(row.payload.get("release"))
            if (
                receipt.run_id != row.run_id
                or receipt.message_id != message.id
                or receipt.generation_id != current
                or receipt.text_sha256 != text_digest(message.text)
                or receipt.citations_sha256 != digest(message.citations)
                or receipt.policy_sha256 != digest(message.answer_policy)
                or receipt.artifacts_sha256 != digest(message.artifacts)
                or row.payload.get("seal_sha256") != digest(receipt.model_dump(mode="json"))
            ):
                continue
            if receipt.outcome == "grounded" and (
                not receipt.fact_ids or not receipt.result_pins or current is None
            ):
                continue
            if any(
                pin.id not in index
                or index[pin.id].run_id != row.run_id
                or digest({"kind": index[pin.id].kind, "payload": index[pin.id].payload}) != pin.sha256
                for pin in receipt.result_pins
            ):
                continue
            return receipt
        except (ValidationError, ValueError, TypeError, KeyError):
            continue
    return None


def legacy_notice(language: str) -> str:
    return (
        "Esta respuesta anterior debe generarse de nuevo a partir de fuentes verificables."
        if language.lower().startswith("es")
        else "This earlier response needs to be generated again from verifiable sources."
    )


def message_language(message: ChatMessage) -> str:
    preferences = message.presentation or {}
    language = preferences.get("response_language", "auto")
    return preferences.get("locale", "en-US") if language == "auto" else language
