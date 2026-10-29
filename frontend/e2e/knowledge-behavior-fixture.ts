// Copyright 2026 Firefly Software Foundation SPDX-License-Identifier: Apache-2.0
// Explicit synthetic organization policy; these values do not describe a running deployment.
export const documents = {
  answer_mode: 'rag',
  retrieval_top_k: 17,
  retrieval_per_query_k: 35,
  retrieval_rrf_k: 61,
  query_expansion_enabled: false,
  query_expansion_n: 3,
  answer_top_k: 10,
  rlm_max_iters: 8,
  rlm_sub_budget: 12,
  rlm_max_depth: 1,
  rlm_self_consistency: 1,
  rlm_extended_reasoning: false,
};
export const structured = {
  top_k_schema: 12,
  top_k_examples: 4,
  top_k_metrics: 3,
  rrf_k: 60,
  generation_candidates: 1,
  max_refine_retries: 2,
  grounding_min_confidence: 0.6,
};
const bounds = (values: Record<string, [number, number]>) =>
  Object.fromEntries(
    Object.entries(values).map(([key, [minimum, maximum]]) => [key, { minimum, maximum }]),
  );
export const knowledgeBehaviorSettings = {
  tenant_id: 'tenant-one',
  schema_version: 1,
  revision: 7,
  origin: 'organization',
  documents,
  structured,
  capabilities: {
    documents: {
      answer_modes: ['rag', 'rlm'],
      rlm_curated_knowledge_supported: false,
      rlm_curated_knowledge_reason: 'KNOWLEDGE_RLM_UNQUALIFIED',
      rlm_model_role: 'documents.rlm',
      rlm_recorded_views_required: true,
      rlm_recorded_views_reason: 'RLM_DOCUMENT_VIEWS_REQUIRED',
      bounds: bounds({
        retrieval_top_k: [1, 200],
        retrieval_per_query_k: [1, 500],
        retrieval_rrf_k: [1, 1000],
        query_expansion_n: [1, 10],
        answer_top_k: [1, 40],
        rlm_max_iters: [1, 64],
        rlm_sub_budget: [0, 128],
        rlm_max_depth: [0, 8],
        rlm_self_consistency: [1, 8],
      }),
    },
    structured: {
      bounds: bounds({
        top_k_schema: [1, 100],
        top_k_examples: [0, 50],
        top_k_metrics: [0, 50],
        rrf_k: [1, 1000],
        generation_candidates: [1, 8],
        max_refine_retries: [0, 8],
        grounding_min_confidence: [0, 1],
      }),
    },
  },
};
