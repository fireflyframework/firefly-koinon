// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;
import java.math.BigDecimal;



/** Typed canonical StructuredKnowledgeSettings contract. */
public record StructuredKnowledgeSettings(
    @JsonProperty("top_k_schema") Integer topKSchema,
    @JsonProperty("top_k_examples") Integer topKExamples,
    @JsonProperty("top_k_metrics") Integer topKMetrics,
    @JsonProperty("rrf_k") Integer rrfK,
    @JsonProperty("generation_candidates") Integer generationCandidates,
    @JsonProperty("max_refine_retries") Integer maxRefineRetries,
    @JsonProperty("grounding_min_confidence") BigDecimal groundingMinConfidence
) {

    public static StructuredKnowledgeSettings empty(){return new StructuredKnowledgeSettings(null,null,null,null,null,null,null);}
    public StructuredKnowledgeSettings withTopKSchema(Integer value){return new StructuredKnowledgeSettings(value,topKExamples,topKMetrics,rrfK,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeSettings withTopKExamples(Integer value){return new StructuredKnowledgeSettings(topKSchema,value,topKMetrics,rrfK,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeSettings withTopKMetrics(Integer value){return new StructuredKnowledgeSettings(topKSchema,topKExamples,value,rrfK,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeSettings withRrfK(Integer value){return new StructuredKnowledgeSettings(topKSchema,topKExamples,topKMetrics,value,generationCandidates,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeSettings withGenerationCandidates(Integer value){return new StructuredKnowledgeSettings(topKSchema,topKExamples,topKMetrics,rrfK,value,maxRefineRetries,groundingMinConfidence);}
    public StructuredKnowledgeSettings withMaxRefineRetries(Integer value){return new StructuredKnowledgeSettings(topKSchema,topKExamples,topKMetrics,rrfK,generationCandidates,value,groundingMinConfidence);}
    public StructuredKnowledgeSettings withGroundingMinConfidence(BigDecimal value){return new StructuredKnowledgeSettings(topKSchema,topKExamples,topKMetrics,rrfK,generationCandidates,maxRefineRetries,value);}
}
