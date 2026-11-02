# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Generated wire fields.

Source: backend/src/koinon/answers/receipts.py
SHA256: 6f89550e366a1ebab8884a99247d76836de720baee96bb7fbcb788f588333fba

Server authorization and semantic validation remain authoritative.
"""

from typing import Literal

from pydantic import AwareDatetime, Field

from koinon_sdk._base import ResponseModel
from koinon_sdk.evidence import SourceReference


class ResultPin(ResponseModel):
    id: str = Field(min_length=1, max_length=64)
    sha256: str = Field(pattern="^[a-f0-9]{64}$")


class AnswerRelease(ResponseModel):
    version: Literal[1] = 1
    policy_version: Literal["knowledge-only-v1", "knowledge-only-v2"] = "knowledge-only-v1"
    run_id: str = Field(min_length=1, max_length=64)
    message_id: str = Field(min_length=1, max_length=64)
    tenant_id: str = Field(min_length=1, max_length=64)
    generation_id: str | None = None
    publication_sequence: int = Field(ge=1)
    outcome: Literal["grounded", "refused", "review_required", "product_help"]
    text_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    citations_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    artifacts_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    policy_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    fact_ids: tuple[str, ...] = Field(default=(), max_length=80)
    result_pins: tuple[ResultPin, ...] = Field(default=(), max_length=100)
    source_refs: tuple[SourceReference, ...] = Field(default=(), max_length=500)
    created_at: AwareDatetime
