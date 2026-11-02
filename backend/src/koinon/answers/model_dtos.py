# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""New model outputs require language; retained answer plans remain readable."""

from pydantic import Field

from koinon.answers.dtos import EvidenceAnswerPlan
from koinon.answers.language import AnswerLanguage


class ModelAnswerPlan(EvidenceAnswerPlan):
    language: AnswerLanguage = Field(
        description=(
            "Required answer language: en or es. Follow an explicit language request in the current "
            "message first, otherwise its language, then the saved preference. Never omit this field."
        )
    )
