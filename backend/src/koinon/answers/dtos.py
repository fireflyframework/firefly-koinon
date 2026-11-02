# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""The model selects recorded evidence; it cannot supply factual answer prose."""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from koinon.answers.help_dtos import HelpTopic
from koinon.answers.language import AnswerLanguage


class QuoteSelection(BaseModel):
    """An exact passage from an answer_facts entry whose kind is quote."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    fact_id: str = Field(min_length=1, max_length=64, description="Existing ID of a quote fact only.")
    quote: str = Field(
        min_length=1, max_length=8000, description="Exact contiguous substring of that fact's text."
    )


class ValueSelection(BaseModel):
    """A recorded cell or derived value, including strings, selected only by ID."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    fact_id: str = Field(
        min_length=1,
        max_length=64,
        description="Existing ID of a cell or derived fact. The server supplies its recorded value.",
    )


class EvidenceAnswerPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: Literal["answer", "insufficient_evidence", "product_help"]
    help_topic: HelpTopic | None = None
    language: AnswerLanguage | None = None
    quotes: list[QuoteSelection] = Field(
        default_factory=list,
        max_length=16,
        description="Only facts with kind quote. Never put SQL cells or aggregates here.",
    )
    values: list[ValueSelection] = Field(
        default_factory=list,
        max_length=64,
        description="Facts with kind cell or derived, including text cells, counts and totals.",
    )

    @model_validator(mode="after")
    def selected_evidence(self) -> Self:
        if (self.outcome == "product_help") != (self.help_topic is not None):
            raise ValueError("Only product help selects a finite trusted help topic")
        if self.outcome == "answer" and not (self.quotes or self.values):
            raise ValueError("An answer requires a current verified evidence selection")
        if self.outcome != "answer" and (self.quotes or self.values):
            raise ValueError("An insufficient-evidence response cannot introduce facts")
        return self
