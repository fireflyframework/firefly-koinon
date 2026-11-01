# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The model selects recorded evidence; it cannot supply factual answer prose."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QuoteSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fact_id: str = Field(min_length=1, max_length=64)
    quote: str = Field(min_length=1, max_length=8000)


class ValueSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fact_id: str = Field(min_length=1, max_length=64)


class EvidenceAnswerPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: Literal["answer", "insufficient_evidence"]
    quotes: list[QuoteSelection] = Field(default_factory=list, max_length=16)
    values: list[ValueSelection] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def selected_evidence(self) -> Self:
        if self.outcome == "answer" and not (self.quotes or self.values):
            raise ValueError("An answer requires a current verified evidence selection")
        if self.outcome != "answer" and (self.quotes or self.values):
            raise ValueError("An insufficient-evidence response cannot introduce facts")
        return self
