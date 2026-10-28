# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict


class AnswerPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: Literal["grounded", "refused", "review_required"]
    code: str | None = None
    reason: str | None = None
