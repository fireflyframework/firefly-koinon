// Copyright 2026 Firefly Software Foundation
// SPDX-License-Identifier: Apache-2.0
package org.fireflyframework.koinon.sdk.model;
import com.fasterxml.jackson.annotation.JsonProperty;



/** Typed canonical DocumentKnowledgeBounds contract. */
public record DocumentKnowledgeBounds(
    @JsonProperty("retrieval_top_k") KnowledgeIntegerBounds retrievalTopK,
    @JsonProperty("retrieval_per_query_k") KnowledgeIntegerBounds retrievalPerQueryK,
    @JsonProperty("retrieval_rrf_k") KnowledgeIntegerBounds retrievalRrfK,
    @JsonProperty("query_expansion_n") KnowledgeIntegerBounds queryExpansionN,
    @JsonProperty("answer_top_k") KnowledgeIntegerBounds answerTopK,
    @JsonProperty("rlm_max_iters") KnowledgeIntegerBounds rlmMaxIters,
    @JsonProperty("rlm_sub_budget") KnowledgeIntegerBounds rlmSubBudget,
    @JsonProperty("rlm_max_depth") KnowledgeIntegerBounds rlmMaxDepth,
    @JsonProperty("rlm_self_consistency") KnowledgeIntegerBounds rlmSelfConsistency
) {

    public static DocumentKnowledgeBounds empty(){return new DocumentKnowledgeBounds(null,null,null,null,null,null,null,null,null);}
    public DocumentKnowledgeBounds withRetrievalTopK(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(value,retrievalPerQueryK,retrievalRrfK,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withRetrievalPerQueryK(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,value,retrievalRrfK,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withRetrievalRrfK(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,retrievalPerQueryK,value,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withQueryExpansionN(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,retrievalPerQueryK,retrievalRrfK,value,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withAnswerTopK(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionN,value,rlmMaxIters,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withRlmMaxIters(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionN,answerTopK,value,rlmSubBudget,rlmMaxDepth,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withRlmSubBudget(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionN,answerTopK,rlmMaxIters,value,rlmMaxDepth,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withRlmMaxDepth(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,value,rlmSelfConsistency);}
    public DocumentKnowledgeBounds withRlmSelfConsistency(KnowledgeIntegerBounds value){return new DocumentKnowledgeBounds(retrievalTopK,retrievalPerQueryK,retrievalRrfK,queryExpansionN,answerTopK,rlmMaxIters,rlmSubBudget,rlmMaxDepth,value);}
}
