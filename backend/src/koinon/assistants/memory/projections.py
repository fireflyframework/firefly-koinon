# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Internal immutable query projections; these are never SDK wire models."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True, slots=True)
class MemoryCandidate:
    run_id: str
    thread_id: str
    folder_id: str | None
    scope: dict
    created_at: datetime
    user_message_id: str
    user_text: str
    answer_message_id: str
    answer_text: str
    answer_policy: dict
    private_thread: bool
    conversation_title: str
    user_created_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryAuthorityStamp:
    origin_sha256: str
    caller_sha256: str
    availability: dict[str, str]
    current_sha256: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryCurrentResult:
    id: str
    run_id: str
    kind: str
    payload: dict
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MemoryCurrentEvidence:
    run_id: str
    thread_id: str
    subject: str
    tenant_id: str
    scope: dict
    origin_token_id: str | None
    results: tuple[MemoryCurrentResult, ...]
    asset_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class MemoryOutputCapture:
    run_id: str
    kind: Literal["sequence", "reset"]
    value: int
