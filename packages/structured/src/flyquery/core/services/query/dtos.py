# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Typed application results for structured queries."""

import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class AnswerResult:
    """Full result from QueryService.answer()."""

    query_id: uuid.UUID
    sql: str | None
    execution_status: Literal["OK", "REFINED_OK", "FAILED", "REJECTED_BY_FIREWALL"] | None
    preview: list[dict] | None
    row_count: int | None
    truncated: bool
    elapsed_ms: int | None
    chart_hint: str | None
    explanation: str | None
    clarification: Any  # ClarificationFrame or None
    grounded_summary: dict | None
    snapshot_pins: dict[str, str] = field(default_factory=dict)
