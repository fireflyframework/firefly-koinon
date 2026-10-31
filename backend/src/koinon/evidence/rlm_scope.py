# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Shared value constraints for native and public RLM resource scopes."""

from collections.abc import Sequence
from typing import Annotated

from pydantic import Field

RlmResourceIdentifier = Annotated[str, Field(min_length=1, max_length=64, strict=True)]


def require_rlm_scope(documents: Sequence[str], knowledge: Sequence[str]) -> None:
    if (
        not documents
        and not knowledge
        or len(documents) + len(knowledge) > 500
        or len(set(documents)) != len(documents)
        or len(set(knowledge)) != len(knowledge)
    ):
        raise ValueError("RLM tools require a nonempty, unique, bounded document or knowledge scope")


def require_observed_rlm_scope(
    documents: Sequence[str],
    knowledge: Sequence[str],
    *,
    document_sources: set[str],
    knowledge_items: set[str],
) -> None:
    require_rlm_scope(documents, knowledge)
    if not set(documents) <= document_sources or not set(knowledge) <= knowledge_items:
        raise ValueError("RLM tool scope requires observed admission in the same provenance domain")
