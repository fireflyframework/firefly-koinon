# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TitleText(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def normalize(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("A title is required")
        return value


class TitleSuggestion(TitleText):
    based_on_revision: int = Field(ge=1, strict=True)
