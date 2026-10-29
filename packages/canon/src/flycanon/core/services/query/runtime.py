# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Bounded query options and request-local services over shared corpus resources."""

from copy import copy
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from flycanon.config import CanonSettings
from flycanon.core.services.query.answer_dispatcher import AnswerDispatcher
from flycanon.core.services.query.search_service import SearchService
from flycanon.core.services.retrieval.query_expander import QueryExpander
from flycanon.core.services.retrieval.retrieval_service import RetrievalService


class DocumentQueryOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    answer_mode: Literal["rag", "rlm"]
    retrieval_top_k: int = Field(ge=1, le=200, strict=True)
    retrieval_per_query_k: int = Field(ge=1, le=500, strict=True)
    retrieval_rrf_k: int = Field(ge=1, le=1000, strict=True)
    query_expansion_enabled: bool = Field(strict=True)
    query_expansion_n: int = Field(ge=1, le=10, strict=True)
    answer_top_k: int = Field(ge=1, le=40, strict=True)
    rlm_max_iters: int = Field(ge=1, le=64, strict=True)
    rlm_sub_budget: int = Field(ge=0, le=128, strict=True)
    rlm_max_depth: int = Field(ge=0, le=8, strict=True)
    rlm_self_consistency: int = Field(ge=1, le=8, strict=True)
    rlm_extended_reasoning: bool = Field(strict=True)

    def settings(self, baseline: CanonSettings) -> CanonSettings:
        return baseline.model_copy(update=self.model_dump(exclude={"answer_top_k", "rlm_extended_reasoning"}))


def _retrieval(base: RetrievalService, settings: CanonSettings) -> RetrievalService:
    selected = copy(base)
    selected._default_top_k = settings.retrieval_top_k
    selected._default_per_query_k = settings.retrieval_per_query_k
    selected._rrf_k = settings.retrieval_rrf_k
    selected._query_expander = (
        QueryExpander(model=settings.answer_model, settings=settings)
        if settings.query_expansion_enabled
        else None
    )
    selected._query_expansion_n = settings.query_expansion_n if selected._query_expander else 1
    return selected


def scoped_search(
    base: SearchService, baseline: CanonSettings, options: DocumentQueryOptions
) -> SearchService:
    selected = copy(base)
    selected._retrieval = _retrieval(base._retrieval, options.settings(baseline))
    return selected


def scoped_answer(base: AnswerDispatcher, options: DocumentQueryOptions) -> AnswerDispatcher:
    selected = copy(base)
    selected._settings = options.settings(base._settings)
    selected._rag = copy(base._rag)
    selected._rag._settings = selected._settings
    selected._rag._retrieval = _retrieval(base._rag._retrieval, selected._settings)
    selected._rlm = copy(base._rlm)
    selected._rlm._settings = selected._settings
    return selected
