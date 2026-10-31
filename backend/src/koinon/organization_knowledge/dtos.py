# Copyright 2026 Firefly Software Foundation
# SPDX-License-Identifier: Apache-2.0
"""Concrete organization policy; deployment resources and secrets are never public settings."""

from hashlib import sha256
from json import dumps
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgePolicyValue(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DocumentKnowledgeSettings(KnowledgePolicyValue):
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


class StructuredKnowledgeSettings(KnowledgePolicyValue):
    top_k_schema: int = Field(ge=1, le=100, strict=True)
    top_k_examples: int = Field(ge=0, le=50, strict=True)
    top_k_metrics: int = Field(ge=0, le=50, strict=True)
    rrf_k: int = Field(ge=1, le=1000, strict=True)
    generation_candidates: int = Field(ge=1, le=8, strict=True)
    max_refine_retries: int = Field(ge=0, le=8, strict=True)
    grounding_min_confidence: float = Field(ge=0, le=1, strict=True, allow_inf_nan=False)


class KnowledgeIntegerBounds(KnowledgePolicyValue):
    minimum: int = Field(strict=True)
    maximum: int = Field(strict=True)


class KnowledgeNumberBounds(KnowledgePolicyValue):
    minimum: float = Field(strict=True, allow_inf_nan=False)
    maximum: float = Field(strict=True, allow_inf_nan=False)


class DocumentKnowledgeBounds(KnowledgePolicyValue):
    retrieval_top_k: KnowledgeIntegerBounds
    retrieval_per_query_k: KnowledgeIntegerBounds
    retrieval_rrf_k: KnowledgeIntegerBounds
    query_expansion_n: KnowledgeIntegerBounds
    answer_top_k: KnowledgeIntegerBounds
    rlm_max_iters: KnowledgeIntegerBounds
    rlm_sub_budget: KnowledgeIntegerBounds
    rlm_max_depth: KnowledgeIntegerBounds
    rlm_self_consistency: KnowledgeIntegerBounds


class StructuredKnowledgeBounds(KnowledgePolicyValue):
    top_k_schema: KnowledgeIntegerBounds
    top_k_examples: KnowledgeIntegerBounds
    top_k_metrics: KnowledgeIntegerBounds
    rrf_k: KnowledgeIntegerBounds
    generation_candidates: KnowledgeIntegerBounds
    max_refine_retries: KnowledgeIntegerBounds
    grounding_min_confidence: KnowledgeNumberBounds


class DocumentKnowledgeCapabilities(KnowledgePolicyValue):
    """Feature availability; model/provider readiness requires separate installation qualification."""

    answer_modes: list[Literal["rag", "rlm"]]
    rlm_curated_knowledge_supported: bool = Field(strict=True)
    rlm_curated_knowledge_reason: Literal["KNOWLEDGE_RLM_UNQUALIFIED"] | None
    rlm_model_role: Literal["documents.rlm"]
    rlm_recorded_views_required: Literal[True]
    rlm_recorded_views_reason: Literal["RLM_DOCUMENT_VIEWS_REQUIRED"]
    bounds: DocumentKnowledgeBounds

    @model_validator(mode="after")
    def coherent_curated_support(self) -> Self:
        if self.rlm_curated_knowledge_supported != (self.rlm_curated_knowledge_reason is None):
            raise ValueError("Curated RLM support and its qualification reason must agree")
        return self


class StructuredKnowledgeCapabilities(KnowledgePolicyValue):
    bounds: StructuredKnowledgeBounds


class OrganizationKnowledgeCapabilities(KnowledgePolicyValue):
    documents: DocumentKnowledgeCapabilities
    structured: StructuredKnowledgeCapabilities


class OrganizationKnowledgeSettings(KnowledgePolicyValue):
    tenant_id: str = Field(min_length=1, max_length=64)
    schema_version: Literal[1]
    revision: int = Field(ge=0, le=2147483647, strict=True)
    origin: Literal["deployment", "organization"]
    documents: DocumentKnowledgeSettings
    structured: StructuredKnowledgeSettings
    capabilities: OrganizationKnowledgeCapabilities


class OrganizationKnowledgeSettingsInput(KnowledgePolicyValue):
    expected_revision: int = Field(ge=0, le=2147483646, strict=True)
    documents: DocumentKnowledgeSettings
    structured: StructuredKnowledgeSettings


def snapshot_digest(value: dict) -> str:
    return sha256(
        dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    ).hexdigest()


class OrganizationKnowledgeSnapshot(KnowledgePolicyValue):
    tenant_id: str = Field(min_length=1, max_length=64)
    schema_version: Literal[1]
    revision: int = Field(ge=0, le=2147483647, strict=True)
    origin: Literal["deployment", "organization"]
    documents: DocumentKnowledgeSettings
    structured: StructuredKnowledgeSettings
    digest: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def verify_identity(self):
        if (self.revision == 0) != (self.origin == "deployment"):
            raise ValueError("The settings origin must match its recorded revision")
        if self.digest != snapshot_digest(self.model_dump(mode="json", exclude={"digest"})):
            raise ValueError("The effective knowledge settings digest does not match its snapshot")
        return self
