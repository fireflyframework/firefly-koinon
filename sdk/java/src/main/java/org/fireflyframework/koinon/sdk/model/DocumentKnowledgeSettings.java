// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentKnowledgeSettings contract. */
public record DocumentKnowledgeSettings(
    @JsonProperty("answer_mode") KnowledgeAnswerMode answerMode,
    @JsonProperty("retrieval_top_k") Integer retrievalTopK,
    @JsonProperty("retrieval_per_query_k") Integer retrievalPerQueryK,
    @JsonProperty("retrieval_rrf_k") Integer retrievalRrfK,
    @JsonProperty("query_expansion_enabled") Boolean queryExpansionEnabled,
    @JsonProperty("query_expansion_n") Integer queryExpansionN,
    @JsonProperty("answer_top_k") Integer answerTopK,
    @JsonProperty("rlm_max_iters") Integer rlmMaxIters,
    @JsonProperty("rlm_sub_budget") Integer rlmSubBudget,
    @JsonProperty("rlm_max_depth") Integer rlmMaxDepth,
    @JsonProperty("rlm_self_consistency") Integer rlmSelfConsistency,
    @JsonProperty("rlm_extended_reasoning") Boolean rlmExtendedReasoning
) {

    public static DocumentKnowledgeSettings empty(){return new DocumentKnowledgeSettings(null,null,null,null,null,null,null,null,null,null,null,null);}
    public DocumentKnowledgeSettings withAnswerMode(KnowledgeAnswerMode value){return new DocumentKnowledgeSettings(value,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRetrievalTopK(Integer value){return new DocumentKnowledgeSettings(answerMode,value,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRetrievalPerQueryK(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,value,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRetrievalRrfK(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,value,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withQueryExpansionEnabled(Boolean value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,value,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withQueryExpansionN(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,value,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withAnswerTopK(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,value,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRlmMaxIters(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,value,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRlmSubBudget(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,value,rlmMaxDepth,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRlmMaxDepth(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,value,rlmSelfConsistency,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRlmSelfConsistency(Integer value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,value,rlmExtendedReasoning);}
    public DocumentKnowledgeSettings withRlmExtendedReasoning(Boolean value){return new DocumentKnowledgeSettings(answerMode,retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionEnabled,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency,value);}
}
