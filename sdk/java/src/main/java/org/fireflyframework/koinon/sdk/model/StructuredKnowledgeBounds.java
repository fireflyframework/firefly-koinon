// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical StructuredKnowledgeBounds contract. */
public record StructuredKnowledgeBounds(
    @JsonProperty("top_k_schema") KnowledgeIntegerBounds topKSchema,
    @JsonProperty("top_k_examples") KnowledgeIntegerBounds topKExamples,
    @JsonProperty("top_k_metrics") KnowledgeIntegerBounds topKMetrics,
    @JsonProperty("rrf_k") KnowledgeIntegerBounds rrfK,
    @JsonProperty("generation_candidates") KnowledgeIntegerBounds generationCandidates,
    @JsonProperty("max_refine_retries") KnowledgeIntegerBounds maxRefineRetries,
    @JsonProperty("grounding_min_confidence") KnowledgeNumberBounds groundingMinConfidence
) {

    public static StructuredKnowledgeBounds empty(){return new StructuredKnowledgeBounds(null,null,null,null,null,null,null);}
    public StructuredKnowledgeBounds withTopKSchema(KnowledgeIntegerBounds value){return new StructuredKnowledgeBounds(value,topKExamples,topKMetrics,rrfK,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeBounds withTopKExamples(KnowledgeIntegerBounds value){return new StructuredKnowledgeBounds(topKSchema,value,topKMetrics,rrfK,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeBounds withTopKMetrics(KnowledgeIntegerBounds value){return new StructuredKnowledgeBounds(topKSchema,topKExamples,value,rrfK,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeBounds withRrfK(KnowledgeIntegerBounds value){return new StructuredKnowledgeBounds(topKSchema,topKExamples,topKMetrics,value,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeBounds withGenerationCandidates(KnowledgeIntegerBounds value){return new StructuredKnowledgeBounds(topKSchema,topKExamples,topKMetrics,rrfK,value,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeBounds withMaxRefineRetries(KnowledgeIntegerBounds value){return new StructuredKnowledgeBounds(topKSchema,topKExamples,topKMetrics,rrfK,generationCandidates,value,groundingMinConfidence);}
    public StructuredKnowledgeBounds withGroundingMinConfidence(KnowledgeNumberBounds value){return new StructuredKnowledgeBounds(topKSchema,topKExamples,topKMetrics,rrfK,generationCandidates,maxRefineRetries,value);}
}
