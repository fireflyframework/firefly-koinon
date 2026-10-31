<!-- Copyright 2026 Firefly Software Foundation -->
<!-- SPDX-License-Identifier: Apache-2.0 -->

# DocumentKnowledgeSettings

[All wire models](index.md)

Model aliases: `DocumentKnowledgeSettings`.

Type: `object`.

## Fields

Required means the key must be present. Nullable means its value may be `null`; it does not make a required key optional. “Not specified” means the schema declares no default.

| Field | Type | Required | Default |
| --- | --- | --- | --- |
| `answer_mode` | `string` | Yes | Not specified |
| `retrieval_top_k` | `integer` | Yes | Not specified |
| `retrieval_per_query_k` | `integer` | Yes | Not specified |
| `retrieval_rrf_k` | `integer` | Yes | Not specified |
| `query_expansion_enabled` | `boolean` | Yes | Not specified |
| `query_expansion_n` | `integer` | Yes | Not specified |
| `answer_top_k` | `integer` | Yes | Not specified |
| `rlm_max_iters` | `integer` | Yes | Not specified |
| `rlm_sub_budget` | `integer` | Yes | Not specified |
| `rlm_max_depth` | `integer` | Yes | Not specified |
| `rlm_self_consistency` | `integer` | Yes | Not specified |
| `rlm_extended_reasoning` | `boolean` | Yes | Not specified |

## Model constraints

- Additional properties: not permitted

## Field constraints

### answer_mode

- Allowed values: `"rag"`, `"rlm"`

### retrieval_top_k

- Minimum: `1`
- Maximum: `200`

### retrieval_per_query_k

- Minimum: `1`
- Maximum: `500`

### retrieval_rrf_k

- Minimum: `1`
- Maximum: `1000`

### query_expansion_n

- Minimum: `1`
- Maximum: `10`

### answer_top_k

- Minimum: `1`
- Maximum: `40`

### rlm_max_iters

- Minimum: `1`
- Maximum: `64`

### rlm_sub_budget

- Minimum: `0`
- Maximum: `128`

### rlm_max_depth

- Minimum: `0`
- Maximum: `8`

### rlm_self_consistency

- Minimum: `1`
- Maximum: `8`


## Exact JSON Schema

This is a schema definition, not an example request. It preserves all declared keywords, including constraints not summarized above.

??? note "Complete JSON Schema"

    ```json
    {
      "additionalProperties": false,
      "properties": {
        "answer_mode": {
          "enum": [
            "rag",
            "rlm"
          ],
          "title": "Answer Mode",
          "type": "string"
        },
        "retrieval_top_k": {
          "maximum": 200,
          "minimum": 1,
          "title": "Retrieval Top K",
          "type": "integer"
        },
        "retrieval_per_query_k": {
          "maximum": 500,
          "minimum": 1,
          "title": "Retrieval Per Query K",
          "type": "integer"
        },
        "retrieval_rrf_k": {
          "maximum": 1000,
          "minimum": 1,
          "title": "Retrieval Rrf K",
          "type": "integer"
        },
        "query_expansion_enabled": {
          "title": "Query Expansion Enabled",
          "type": "boolean"
        },
        "query_expansion_n": {
          "maximum": 10,
          "minimum": 1,
          "title": "Query Expansion N",
          "type": "integer"
        },
        "answer_top_k": {
          "maximum": 40,
          "minimum": 1,
          "title": "Answer Top K",
          "type": "integer"
        },
        "rlm_max_iters": {
          "maximum": 64,
          "minimum": 1,
          "title": "Rlm Max Iters",
          "type": "integer"
        },
        "rlm_sub_budget": {
          "maximum": 128,
          "minimum": 0,
          "title": "Rlm Sub Budget",
          "type": "integer"
        },
        "rlm_max_depth": {
          "maximum": 8,
          "minimum": 0,
          "title": "Rlm Max Depth",
          "type": "integer"
        },
        "rlm_self_consistency": {
          "maximum": 8,
          "minimum": 1,
          "title": "Rlm Self Consistency",
          "type": "integer"
        },
        "rlm_extended_reasoning": {
          "title": "Rlm Extended Reasoning",
          "type": "boolean"
        }
      },
      "required": [
        "answer_mode",
        "retrieval_top_k",
        "retrieval_per_query_k",
        "retrieval_rrf_k",
        "query_expansion_enabled",
        "query_expansion_n",
        "answer_top_k",
        "rlm_max_iters",
        "rlm_sub_budget",
        "rlm_max_depth",
        "rlm_self_consistency",
        "rlm_extended_reasoning"
      ],
      "title": "DocumentKnowledgeSettings",
      "type": "object"
    }
    ```
