# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from koinon.answers.publication_dtos import AnswerPublication


class AnswerSelectionValidation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    repairs: int = Field(ge=0, le=1)
    errors: list[str] = Field(default_factory=list, max_length=2)


class AnswerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: Literal["grounded", "refused", "review_required", "product_help"]
    code: str | None = None
    reason: str | None = None
    validation: AnswerSelectionValidation | None = None
    publication: AnswerPublication | None = None
