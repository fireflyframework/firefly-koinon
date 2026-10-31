<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentKnowledgeBounds

[All wire models](index.md)

Model aliases: `DocumentKnowledgeBounds`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `retrieval_top_k` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `retrieval_per_query_k` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `retrieval_rrf_k` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `query_expansion_n` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `answer_top_k` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `rlm_max_iters` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `rlm_sub_budget` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `rlm_max_depth` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |
| `rlm_self_consistency` | [`KnowledgeIntegerBounds`](knowledgeintegerbounds.md) | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "retrieval_top_k": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "retrieval_per_query_k": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "retrieval_rrf_k": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "query_expansion_n": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "answer_top_k": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "rlm_max_iters": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "rlm_sub_budget": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "rlm_max_depth": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        },
        "rlm_self_consistency": {
          "$ref": "#/$defs/KnowledgeIntegerBounds"
        }
      },
      "required": [
        "retrieval_top_k",
        "retrieval_per_query_k",
        "retrieval_rrf_k",
        "query_expansion_n",
        "answer_top_k",
        "rlm_max_iters",
        "rlm_sub_budget",
        "rlm_max_depth",
        "rlm_self_consistency"
      ],
      "title": "DocumentKnowledgeBounds",
      "type": "object"
    }
    ```
