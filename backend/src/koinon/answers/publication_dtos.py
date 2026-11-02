# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnswerPublication(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    format: Literal["verified-unicode-v1"]
    chunk_size: Literal[128]
    chunk_count: int = Field(ge=1, le=2000)
    text_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
